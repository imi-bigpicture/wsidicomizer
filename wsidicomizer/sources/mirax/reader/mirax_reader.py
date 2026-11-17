#    Copyright 2026 SECTRA AB
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""MiraxReader: file access, decoding and caching of a slide's stored tiles.

The tile layout (photo positions) lives in tile_layout.MiraxTileLayout; regions are
composed from it by wsidicomizer.image_data.ComposedLevelImageData.
"""

from enum import Enum
from pathlib import Path

import numpy as np
from opentile.config import get_settings as get_opentile_settings
from opentile.file import FileHandlePool, LocalFileReader
from opentile.geometry import Point as OpenTilePoint
from opentile.tile_overlap import TileOverlap
from PIL import Image
from wsidicom.cache import LRU, CacheItem
from wsidicom.geometry import Point, Size

from wsidicomizer.sources.mirax.reader.decoder import MiraxDecoderFactory
from wsidicomizer.sources.mirax.reader.errors import MrxsError
from wsidicomizer.sources.mirax.reader.index import BlobLocation, MiraxIndex
from wsidicomizer.sources.mirax.reader.slidedat import Channel, Slidedat
from wsidicomizer.sources.mirax.reader.tile_layout import MiraxTileLayout


class MiraxAssociatedImageType(Enum):
    """The associated images a MIRAX slide can hold. Each value is the image's
    nonhierarchical value name in the slide's index."""

    LABEL = "ScanDataLayer_SlideBarcode"
    MACRO = "ScanDataLayer_SlideThumbnail"
    THUMBNAIL = "ScanDataLayer_SlidePreview"
    """Preview covering the whole nominal camera grid (`scan_dimensions`)."""


class MiraxReader:
    """Read the stored tiles of a MIRAX slide.

    Only the base level is read: the stored lower-resolution levels are mosaics
    of camera photos at fractional positions, so the pyramid is rebuilt from the
    base. `overlap` places the base level's stored tiles on the de-overlapped
    canvas, and `decode_tile` decodes one. Tiles decode to (H, W, 3) arrays: RGB
    for brightfield, up to three fluorescence channels packed in BGR order
    otherwise. Arrays are `dtype`: uint8 for 8-bit slides, uint16 for 16-bit
    fluorescence.
    """

    def __init__(self, path: str | Path, tile_cache: int = 64):
        """Open a MIRAX slide.

        Parameters
        ----------
        path: str | Path
            Path to the .mrxs file.
        tile_cache: int
            Number of decoded tiles kept in an LRU cache. Adjacent regions
            (raster scanning) share boundary tiles, so this avoids re-decoding
            them. Set larger to reuse tiles across scan rows, 0 to
            disable.
        """
        path = Path(path)
        data_folder = self._find_data_folder(path)
        if data_folder is None:
            raise MrxsError(f"not a .mrxs file with a Slidedat.ini: {path}")

        # each tile counts 1, so the cache holds `tile_cache` tiles
        self._cache = LRU[BlobLocation, np.ndarray](tile_cache)

        self._slidedat = Slidedat(data_folder)
        channels = self._slidedat.channels
        if channels and not self._slidedat.channels_single_leaf:
            raise NotImplementedError(
                f">3-channel fluorescence not supported ({len(channels)} "
                "channels spanning multiple data leaves)"
            )
        self._tile_decoder = MiraxDecoderFactory.for_image_format(
            self._slidedat.image_format
        )
        self._dtype = np.dtype(
            np.uint16 if self._slidedat.bit_depth == 16 else np.uint8
        )
        # one thread-safe handle pool per data file, as opentile reads its files
        self._file_readers: dict[int, LocalFileReader] = {}
        max_handles = get_opentile_settings().max_file_handles_per_file
        try:
            for number, datafile_path in self._slidedat.datafiles.items():
                self._file_readers[number] = LocalFileReader(
                    FileHandlePool(str(datafile_path), max_handles)
                )
            self._open_index(data_folder)
        except BaseException:
            self.close()
            raise

    @property
    def overlap(self) -> TileOverlap:
        """Placement of the base level's stored tiles on the de-overlapped canvas,
        keyed by (col, row) grid position."""
        return self._tile_layout.overlap

    @property
    def dtype(self) -> np.dtype:
        """The dtype tiles decode to: uint8 for 8-bit slides, uint16 for 16-bit."""
        return self._dtype

    @property
    def dimensions(self) -> Size:
        """Size of the base level."""
        dimensions = self._tile_layout.dimensions
        return Size(dimensions.width, dimensions.height)

    @property
    def bounds_offset(self) -> Point:
        """Level-0 position of the tissue bounding box in the slide's scan
        coordinates; read coordinates are relative to it (openslide's bounds-x/y).
        """
        origin = self._tile_layout.origin
        return Point(origin.x, origin.y)

    @property
    def scan_dimensions(self) -> Size:
        """Level-0 size of the nominal camera grid, the extent the SlidePreview
        (`thumbnail`) associated image covers (openslide's level-0 dimensions);
        the tissue bounding box lies within it at `bounds_offset`.
        """
        slidedat = self._slidedat
        tile_size = slidedat.tile_size
        overlap = slidedat.overlap
        photos_x = slidedat.imagenumber_x // slidedat.divisions
        photos_y = slidedat.imagenumber_y // slidedat.divisions
        return Size(
            round(
                slidedat.imagenumber_x * tile_size.width - (photos_x - 1) * overlap.x
            ),
            round(
                slidedat.imagenumber_y * tile_size.height - (photos_y - 1) * overlap.y
            ),
        )

    @property
    def fill_color(self) -> tuple[int, int, int]:
        """Background fill as RGB (from IMAGE_FILL_COLOR_BGR): white brightfield,
        black fluorescence."""
        packed = self._slidedat.fill_bgr
        return (packed & 0xFF, (packed >> 8) & 0xFF, (packed >> 16) & 0xFF)

    @property
    def slidedat(self) -> Slidedat:
        """The slide's `Slidedat` (geometry + typed metadata accessors)."""
        return self._slidedat

    @property
    def channels(self) -> list[Channel]:
        """Fluorescence channels (empty for brightfield), each a band of the
        decoded tiles."""
        return self._slidedat.channels

    @property
    def associated_images(self) -> dict[MiraxAssociatedImageType, Image.Image]:
        """The associated images present in the slide, decoded on each access."""
        images: dict[MiraxAssociatedImageType, Image.Image] = {}
        for image_type in MiraxAssociatedImageType:
            location = self._index.nonhierarchical.get(image_type.value)
            if location is not None:
                images[image_type] = self._open_associated(self._read(location))
        return images

    @classmethod
    def is_supported(cls, path: str | Path) -> bool:
        """Check whether `path` is a MIRAX slide: a .mrxs file with a Slidedat.ini
        in its data folder. Nothing is parsed, so a slide in a variant the
        reader refuses (reduced pyramid, >3-channel fluorescence, tiles without
        recorded positions, more than one position buffer) passes it, and opening
        it raises `NotImplementedError`.

        Parameters
        ----------
        path: str | Path
            Path to check.

        Returns
        -------
        bool
            True if `path` has the MIRAX file layout.
        """
        return cls._find_data_folder(Path(path)) is not None

    def decode_tile(self, grid_position: OpenTilePoint) -> np.ndarray:
        """Decode the base-level tile at a grid position, cached by location.

        Parameters
        ----------
        grid_position: OpenTilePoint
            (col, row) of the tile on the base level's tile grid.

        Returns
        -------
        np.ndarray
            The decoded (H, W, 3) tile, possibly shared from the cache.
        """
        return self._decode(self._index.tiles[grid_position])

    def close(self) -> None:
        """Close all file handles and clear the tile cache."""
        for reader in self._file_readers.values():
            reader.close()
        self._cache.clear()

    def __enter__(self) -> "MiraxReader":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _open_index(self, data_folder: Path) -> None:
        """Parse the index and the tile placement, rejecting unsupported layouts.

        Parameters
        ----------
        data_folder: Path
            The slide's data folder.
        """
        index_bytes = (data_folder / self._slidedat.index_filename).read_bytes()
        self._index = MiraxIndex(index_bytes, self._slidedat)
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
            position_bytes = self._read(self._index.position_buffer)
        self._tile_layout = MiraxTileLayout(
            self._index.tiles, self._slidedat, position_bytes
        )

    @staticmethod
    def _find_data_folder(path: Path) -> Path | None:
        """Return the folder holding a slide's data files, if `path` is a MIRAX
        slide. Nothing is parsed.

        By the MIRAX convention the data folder is next to the .mrxs file and named
        after it (`CMU-1.mrxs` beside `CMU-1/`), and holds Slidedat.ini, the index
        and the Data*.dat files.

        Parameters
        ----------
        path: Path
            Path to check.

        Returns
        -------
        Path | None
            The slide's data folder, or None if `path` is not a .mrxs file with a
            Slidedat.ini in its data folder.
        """
        if path.suffix.lower() != ".mrxs":
            return None
        data_folder = path.parent / path.stem
        if not (data_folder / "Slidedat.ini").is_file():
            return None
        return data_folder

    def _read(self, location: BlobLocation) -> bytes:
        """Read a stored blob from a data file, thread-safely via pooled handles.

        Parameters
        ----------
        location: BlobLocation
            Where the blob is stored.

        Returns
        -------
        bytes
            The blob's bytes.
        """
        return self._file_readers[location.file_number].read(
            location.offset, location.length
        )

    def _decode(self, location: BlobLocation) -> np.ndarray:
        """Decode a tile to a numpy array, cached by location.

        Thread-safe: the cache locks only around its own bookkeeping, and the
        decode (which releases the GIL) runs outside it, so concurrent decodes
        scale across cores; a lost race only decodes a tile twice.
        Callers must not mutate the returned array, which the cache shares.

        Parameters
        ----------
        location: BlobLocation
            Where the tile is stored.

        Returns
        -------
        np.ndarray
            The decoded (H, W, 3) tile, possibly shared from the cache.
        """
        if not self._cache.maxsize:  # no cache: decode straight through
            return self._decode_stored(location)
        tile = self._cache.get(location)
        if tile is None:
            tile = self._decode_stored(location)
            self._cache.put(location, CacheItem(tile, 1))
        return tile

    def _decode_stored(self, location: BlobLocation) -> np.ndarray:
        """Read and decode a stored tile, checking its shape and bit depth.

        A tile is placed whole on a canvas of the slide's stated bit depth. A
        tile smaller than the slide's tile size, or not of three samples, would
        fail to paste, and a tile of another dtype would be cast without a word
        (a 16-bit tile into an 8-bit canvas wraps its values).

        Parameters
        ----------
        location: BlobLocation
            Where the tile is stored.

        Returns
        -------
        np.ndarray
            The decoded (H, W, 3) tile.

        Raises
        ------
        MrxsError
            If the tile does not decode to three samples of at least the slide's
            tile size, or to the dtype of the slide's bit depth.
        """
        tile = self._tile_decoder.decode(self._read(location))
        tile_size = self._slidedat.tile_size
        if (
            tile.ndim != 3
            or tile.shape[2] != 3
            or tile.shape[0] < tile_size.height
            or tile.shape[1] < tile_size.width
        ):
            raise MrxsError(
                f"tile decodes to shape {tile.shape}, but the slide states a tile "
                f"size of {tile_size.width}x{tile_size.height} with 3 samples"
            )
        if tile.dtype != self._dtype:
            raise MrxsError(
                f"tile decodes to {tile.dtype}, but the slide states a bit depth of "
                f"{self._slidedat.bit_depth} ({self._dtype})"
            )
        return tile

    @staticmethod
    def _open_associated(blob: bytes) -> Image.Image:
        """Decode an associated-image blob to a Pillow image, with the decoder
        its magic bytes name (associated images carry their own format).

        Parameters
        ----------
        blob: bytes
            The stored associated-image bytes.

        Returns
        -------
        Image.Image
            The decoded image.
        """
        decoder = MiraxDecoderFactory.for_blob(blob)
        return Image.fromarray(decoder.decode(blob))
