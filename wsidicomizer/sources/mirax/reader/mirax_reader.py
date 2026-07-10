"""MiraxReader: file access, decoding, caching, and the read API.

Tile placement (positions, overlaps, the spatial index) lives in
placement.TilePlacement; this module composes decoded tiles into regions.
"""

import threading
from collections import OrderedDict
from pathlib import Path

import imagecodecs
import numpy as np
from opentile.file import LocalFileReader
from PIL import Image

from wsidicomizer.sources.mirax.reader.errors import MrxsError
from wsidicomizer.sources.mirax.reader.index import Loc, MiraxIndex
from wsidicomizer.sources.mirax.reader.placement import TilePlacement
from wsidicomizer.sources.mirax.reader.slidedat import Channel, Slidedat

# Decode a stored tile blob to a numpy array, dispatched on IMAGE_FORMAT. A
# specific decoder (not imagecodecs.imread) skips format sniffing and its noise.
# 8-bit formats decode to uint8 (H, W, 3); 16-bit ones to uint16 (H, W, 3).
_TILE_DECODERS = {
    "JPEG": imagecodecs.jpeg_decode,
    "JPEG_RGB": imagecodecs.jpeg_decode,
    "BMP24": imagecodecs.bmp_decode,
    "PNG": imagecodecs.png_decode,
    "JPEGXR": imagecodecs.jpegxr_decode,
    "JPEG2000": imagecodecs.jpeg2k_decode,
}

# Associated images carry their own format (independent of the tile IMAGE_FORMAT),
# so they're decoded by magic bytes. Same imagecodecs path as the tiles, dispatched
# without imagecodecs.imread's format sniffing (and its EXR-probe noise).
_MAGIC_DECODERS = (
    (b"\xff\xd8\xff", imagecodecs.jpeg_decode),
    (b"\x89PNG", imagecodecs.png_decode),
    (b"\x49\x49\xbc\x01", imagecodecs.jpegxr_decode),
    (b"\x00\x00\x00\x0c", imagecodecs.jpeg2k_decode),
    (b"BM", imagecodecs.bmp_decode),
)


class MiraxReader:
    """Read a MIRAX slide.

    Coordinates are level-local: read_region(level, location, size) takes both
    location and size in that level's own pixels; get_tile(level, col, row) indexes
    a tile grid on the level. Regions are numpy arrays — (H, W, 3) for the packed
    tile (RGB for brightfield), and read_channel splits one grayscale (H, W) plane
    out of it. Arrays are uint8 for 8-bit slides, uint16 for 16-bit fluorescence.
    """

    def __init__(self, path: str | Path, tile_cache: int = 64):
        """Open a MIRAX slide.

        Parameters
        ----------
        path: str | Path
            Path to the .mrxs file.
        tile_cache: int
            Number of decoded tiles kept in an LRU cache. Adjacent read_region
            calls (raster scanning) share boundary tiles, so this avoids
            re-decoding them. Set larger to reuse tiles across scan rows, 0 to
            disable.
        """
        path = Path(path)
        if path.suffix.lower() != ".mrxs":
            raise MrxsError(f"not a .mrxs file: {path}")
        directory = path.with_suffix("")

        self._cache: OrderedDict[Loc, np.ndarray] = OrderedDict()
        self._cache_max = tile_cache
        self._cache_lock = threading.Lock()
        self._templates: dict[tuple[int, int], np.ndarray] = {}  # shared fill canvases

        self._meta = Slidedat(directory)
        self._decode_tile = _TILE_DECODERS.get(
            self._meta.image_format, imagecodecs.imread
        )
        self._dtype = np.uint16 if self._meta.bit_depth == 16 else np.uint8
        self._fill = np.array(self.fill_color, dtype=self._dtype)
        # one thread-safe handle pool per data file (opentile.LocalFileReader)
        self._readers = {
            number: LocalFileReader(str(datafile_path))
            for number, datafile_path in self._meta.datafiles.items()
        }

        index_bytes = (directory / self._meta.index_filename).read_bytes()
        self._index = MiraxIndex(index_bytes, self._meta)
        # Reject reduced/truncated pyramids (bottom levels dropped, e.g. a
        # "*-Saved-1_16" re-export): the finest level's tiles are 2**base_shift-
        # spaced and the position buffer is at the reduced scale, so correct
        # placement would need two coordinate scales. Fail loud instead.
        if self._index.base_shift:
            raise NotImplementedError(
                f"reduced/truncated MIRAX pyramid (base_shift="
                f"{self._index.base_shift}); only native-resolution slides supported"
            )
        position_bytes = None
        if self._index.position_buffer is not None:
            position_bytes = self._read(*self._index.position_buffer)
        self._placement = TilePlacement(self._index, self._meta, position_bytes)

    @staticmethod
    def is_supported(path: str | Path) -> bool:
        """Cheaply check whether `path` looks like a MIRAX slide.

        Only checks that it's a .mrxs file whose sibling data directory holds a
        Slidedat.ini; it does not parse the index, so it can't tell whether the
        pyramid is a supported (non-reduced) variant.

        Parameters
        ----------
        path: str | Path
            Path to check.

        Returns
        -------
        bool
            True if `path` is a .mrxs file with a Slidedat.ini alongside it.
        """
        path = Path(path)
        return (
            path.suffix.lower() == ".mrxs"
            and (path.with_suffix("") / "Slidedat.ini").is_file()
        )

    # ---- data access ---------------------------------------------------

    def _read(self, file_number: int, offset: int, length: int) -> bytes:
        """Read raw bytes from a data file, thread-safely via pooled handles.

        Parameters
        ----------
        file_number: int
            Index of the Data*.dat file.
        offset: int
            Byte offset to read at.
        length: int
            Number of bytes to read.

        Returns
        -------
        bytes
            The requested bytes.
        """
        return self._readers[file_number].read(offset, length)

    def _decode(self, loc: Loc) -> np.ndarray:
        """Decode a tile to a numpy array, cached by location.

        Thread-safe: the cache dict is touched under a lock but the decode (which
        releases the GIL) runs outside it, so concurrent decodes scale across cores.
        Callers must not mutate the returned array (read_region only reads from it).

        Parameters
        ----------
        loc: Loc
            (file number, offset, length) of the stored tile.

        Returns
        -------
        np.ndarray
            The decoded (H, W, 3) tile, possibly shared from the cache.
        """
        if not self._cache_max:  # no cache: decode straight through, no locking
            return self._decode_tile(self._read(*loc))
        cache = self._cache
        with self._cache_lock:
            tile = cache.get(loc)
            if tile is not None:
                cache.move_to_end(loc)
                return tile
        tile = self._decode_tile(self._read(*loc))
        with self._cache_lock:
            cache[loc] = tile
            if len(cache) > self._cache_max:
                cache.popitem(last=False)
        return tile

    def _template(self, width: int, height: int) -> np.ndarray:
        """Return a shared, READ-ONLY fill canvas for a size, cached per size.

        Callers `.copy()` it for a mutable region — copying a pre-filled array is
        faster than re-filling one each call.

        Parameters
        ----------
        width: int
            Canvas width in pixels.
        height: int
            Canvas height in pixels.

        Returns
        -------
        np.ndarray
            The shared (height, width, 3) fill canvas; do not mutate.
        """
        key = (width, height)
        template = self._templates.get(key)
        if template is None:
            template = np.empty((height, width, 3), dtype=self._dtype)
            template[:] = self._fill  # fill color broadcasts; done once per size
            self._templates[key] = template
        return template

    @staticmethod
    def _paste(out: np.ndarray, tile: np.ndarray, left: int, top: int) -> None:
        """Slice-assign `tile` into `out` at (left, top), clipped to `out`.

        Parameters
        ----------
        out: np.ndarray
            Destination region.
        tile: np.ndarray
            Source tile to place.
        left: int
            Destination x of the tile's top-left (may be negative / off-edge).
        top: int
            Destination y of the tile's top-left.
        """
        height, width = out.shape[0], out.shape[1]
        tile_height, tile_width = tile.shape[0], tile.shape[1]
        x0, y0 = max(left, 0), max(top, 0)
        x1, y1 = min(left + tile_width, width), min(top + tile_height, height)
        if x1 <= x0 or y1 <= y0:
            return
        out[y0:y1, x0:x1] = tile[y0 - top : y1 - top, x0 - left : x1 - left]

    # ---- pyramid / read API -------------------------------------------

    @property
    def level_count(self) -> int:
        return len(self._index.levels)

    @property
    def level_dimensions(self) -> tuple[tuple[int, int], ...]:
        return tuple(self._placement.level_dimensions)

    @property
    def dimensions(self) -> tuple[int, int]:
        return self._placement.level_dimensions[0]

    @property
    def level_downsamples(self) -> tuple[float, ...]:
        return tuple(float(2**level) for level in range(self.level_count))

    @property
    def fill_color(self) -> tuple[int, int, int]:
        """Background fill as RGB (from IMAGE_FILL_COLOR_BGR): white brightfield,
        black fluorescence."""
        packed = self._meta.fill_bgr
        return (packed & 0xFF, (packed >> 8) & 0xFF, (packed >> 16) & 0xFF)

    def get_best_level_for_downsample(self, downsample: float) -> int:
        """Return the highest level whose downsample is <= `downsample`.

        Parameters
        ----------
        downsample: float
            Target downsample factor.

        Returns
        -------
        int
            The best level index.
        """
        best = 0
        for level, level_downsample in enumerate(self.level_downsamples):
            if level_downsample <= downsample:
                best = level
        return best

    @property
    def slidedat(self) -> Slidedat:
        """The parsed Slidedat.ini (geometry + typed metadata accessors)."""
        return self._meta

    @property
    def channels(self) -> list[Channel]:
        """Fluorescence channels (empty for brightfield). See read_channel."""
        return self._meta.channels

    def read_channel(
        self, level: int, location: tuple[int, int], size: tuple[int, int], channel: int
    ) -> np.ndarray:
        """Return one fluorescence channel's intensity over a level-local region.

        Channels are packed into the planes of one tile (BGR order,
        band = 2 - STORING_CHANNEL_NUMBER); this composes the packed region and
        returns the channel's plane. Slides whose channels span multiple data
        leaves (>3 channels) raise NotImplementedError.

        Parameters
        ----------
        level: int
            Pyramid level to read.
        location: tuple[int, int]
            Top-left of the region, in level pixels.
        size: tuple[int, int]
            (width, height) of the region, in level pixels.
        channel: int
            Index into .channels.

        Returns
        -------
        np.ndarray
            The channel's intensity as a single-plane (H, W) array (uint8 or
            uint16).
        """
        channels = self._meta.channels
        if not channels:
            raise MrxsError("not a fluorescence slide (no channels)")
        if not self._meta.channels_single_leaf:
            raise NotImplementedError(
                f">3-channel fluorescence not supported ({len(channels)} channels "
                f"spanning multiple data leaves)"
            )
        region = self.read_region(level, location, size)
        return region[:, :, channels[channel].band]

    # associated-image name -> mirax nonhierarchical value name
    _ASSOC = {
        "label": "ScanDataLayer_SlideBarcode",
        "macro": "ScanDataLayer_SlideThumbnail",
        "thumbnail": "ScanDataLayer_SlidePreview",
    }

    @property
    def associated_images(self) -> dict[str, Image.Image]:
        """The label, macro and thumbnail associated images present in the slide."""
        images: dict[str, Image.Image] = {}
        for name, value_name in self._ASSOC.items():
            loc = self._index.nonhier.get(value_name)
            if loc:
                images[name] = self._open_associated(self._read(*loc))
        return images

    @staticmethod
    def _open_associated(blob: bytes) -> Image.Image:
        """Decode an associated-image blob to a Pillow image via imagecodecs,
        dispatched by magic bytes (associated images carry their own format).

        Parameters
        ----------
        blob: bytes
            The stored associated-image bytes.

        Returns
        -------
        Image.Image
            The decoded image.
        """
        for magic, decode in _MAGIC_DECODERS:
            if blob.startswith(magic):
                return Image.fromarray(decode(blob))
        return Image.fromarray(imagecodecs.imread(blob))  # rare: unlisted format

    def read_region(
        self, level: int, location: tuple[int, int], size: tuple[int, int]
    ) -> np.ndarray:
        """Return a composed (H, W, 3) region; empty areas get the slide fill color.

        Parameters
        ----------
        level: int
            Pyramid level to read.
        location: tuple[int, int]
            Top-left of the region, in level pixels.
        size: tuple[int, int]
            (width, height) of the region, in level pixels.

        Returns
        -------
        np.ndarray
            The region as an (H, W, 3) array (uint8, or uint16 for 16-bit slides).
        """
        left, top = location
        width, height = size
        out = self._template(width, height).copy()
        tiles = self._placement.tiles_in(level, left, top, width, height)
        # paste in (tile_y, tile_x) order so overlap seams resolve deterministically
        for tile_y, tile_x, loc in sorted(
            (tile_y, tile_x, loc) for tile_x, tile_y, loc in tiles
        ):
            self._paste(out, self._decode(loc), tile_x - left, tile_y - top)
        return out

    def get_tile(
        self, level: int, col: int, row: int, tile_size: int = 512
    ) -> np.ndarray:
        """Return the (col, row) tile of a `tile_size` grid on `level`.

        Empty grid positions (the ~60% blank on a sparse slide) cost only the fill
        copy; no tile is decoded.

        Parameters
        ----------
        level: int
            Pyramid level to read.
        col: int
            Tile column on the level's `tile_size` grid.
        row: int
            Tile row on the level's `tile_size` grid.
        tile_size: int
            Tile edge in level pixels.

        Returns
        -------
        np.ndarray
            The tile as an (H, W, 3) array.
        """
        left, top = col * tile_size, row * tile_size
        return self.read_region(level, (left, top), (tile_size, tile_size))

    def get_tiles(
        self, level: int, positions: list[tuple[int, int]], tile_size: int = 512
    ) -> list[np.ndarray]:
        """Return a batch of tiles, sharing source-tile decoding across the batch.

        A row or matrix of adjacent tiles decodes each shared source tile once (see
        read_regions), useful for a memory-constrained worker running tile_cache=0.

        Parameters
        ----------
        level: int
            Pyramid level to read.
        positions: list[tuple[int, int]]
            (col, row) tiles on the level's `tile_size` grid.
        tile_size: int
            Tile edge in level pixels.

        Returns
        -------
        list[np.ndarray]
            One (H, W, 3) array per position, in order.
        """
        locations = [(col * tile_size, row * tile_size) for col, row in positions]
        return self.read_regions(level, locations, (tile_size, tile_size))

    def read_regions(
        self, level: int, locations: list[tuple[int, int]], size: tuple[int, int]
    ) -> list[np.ndarray]:
        """Return a batch of same-sized regions, decoding each source tile once.

        Each source tile is pasted into every output that needs it, so a row/matrix
        of adjacent regions never re-decodes shared tiles, independent of the LRU
        cache.

        Parameters
        ----------
        level: int
            Pyramid level to read.
        locations: list[tuple[int, int]]
            Top-left of each region, in level pixels.
        size: tuple[int, int]
            (width, height) shared by every region, in level pixels.

        Returns
        -------
        list[np.ndarray]
            One (H, W, 3) array per location, in order.
        """
        width, height = size
        outs = [self._template(width, height).copy() for _ in locations]
        # source tile -> (abs tile_y, abs tile_x, [(out_index, paste_x, paste_y), ...])
        targets: dict[Loc, tuple[int, int, list[tuple[int, int, int]]]] = {}
        for out_index, (left, top) in enumerate(locations):
            tiles = self._placement.tiles_in(level, left, top, width, height)
            for tile_x, tile_y, loc in tiles:
                targets.setdefault(loc, (tile_y, tile_x, []))[2].append(
                    (out_index, tile_x - left, tile_y - top)
                )
        # decode once per tile, in global (tile_y, tile_x) order to match read_region
        ordered = sorted(targets.items(), key=lambda item: item[1][:2])
        for loc, (_tile_y, _tile_x, dests) in ordered:
            tile = self._decode(loc)
            for dest_index, paste_x, paste_y in dests:
                self._paste(outs[dest_index], tile, paste_x, paste_y)
        return outs

    def get_thumbnail(self, size: tuple[int, int]) -> Image.Image:
        """Return an RGB thumbnail fitting within `size` (8-bit slides only).

        Parameters
        ----------
        size: tuple[int, int]
            Maximum (width, height) of the thumbnail.

        Returns
        -------
        Image.Image
            The thumbnail as an RGB image.
        """
        dimensions = self._placement.level_dimensions
        level = self.get_best_level_for_downsample(
            max(dimensions[0][0] / size[0], dimensions[0][1] / size[1])
        )
        thumbnail = Image.fromarray(self.read_region(level, (0, 0), dimensions[level]))
        thumbnail.thumbnail(size)
        return thumbnail

    def close(self) -> None:
        """Close all file handles and clear the tile cache."""
        for reader in self._readers.values():
            reader.close()
        with self._cache_lock:
            self._cache.clear()

    def __enter__(self) -> "MiraxReader":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
