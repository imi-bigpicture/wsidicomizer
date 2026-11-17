#    Copyright 2021, 2022, 2023 SECTRA AB
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

"""Base ImageData classes for non-DICOM source adapters."""

from abc import abstractmethod

import numpy as np
from opentile.geometry import Point as OpenTilePoint
from opentile.geometry import Region as OpenTileRegion
from opentile.geometry import Size as OpenTileSize
from opentile.tile_overlap import TileOverlap
from PIL.Image import Image
from pydicom.uid import UID
from wsidicom import ImageData
from wsidicom.cache import LRU, CacheItem
from wsidicom.codec import Encoder
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem, LossyCompression
from wsidicom.thread import ReadExecutor

from wsidicomizer.config import get_settings
from wsidicomizer.overlap_index import OverlapIndex, Placement


class BaseDicomizerImageData(ImageData):
    """
    Base class for Dicomizer image data. Subclasses should implement all the abstract
    methods and properties in the base ImageData-class.
    """

    _blank_encoded_frames: dict[tuple[Size, int | tuple[int, ...]], bytes] | None = None
    _blank_decoded_frames: (
        dict[tuple[Size, int | tuple[int, ...]], np.ndarray] | None
    ) = None

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem | None:
        """Return a default ImageCoordinateSystem."""
        return None

    @property
    def bits(self) -> int:
        return self.encoder.bits

    @property
    def lossy_compression(
        self,
    ) -> list[LossyCompression] | None:
        """Return None as image compression is for most format not known."""
        return None

    @property
    def transcoder(self) -> Encoder | None:
        """Return encoder as for most format transcoding is used."""
        return self.encoder

    def _encode(self, image_data: np.ndarray) -> bytes:
        """Return image data encoded in jpeg using set quality and subsample
        options.

        Parameters
        ----------
        image_data: np.ndarray
            Image data to encode.

        Returns
        ----------
        bytes
            Jpeg bytes.
        """
        return self.encoder.encode(image_data)

    def _get_blank_encoded_frame(
        self, size: Size, fill: int | tuple[int, ...] | None = None
    ) -> bytes:
        """Return the encoded blank frame of a size, cached per size and fill.

        Parameters
        ----------
        size: Size
            Size of frame to get.
        fill: int | tuple[int, ...] | None = None
            Value to fill the frame with, or None for the blank color.

        Returns
        ----------
        bytes
            Encoded blank frame.
        """
        if self._blank_encoded_frames is None:
            self._blank_encoded_frames = {}
        key = (size, self.blank_color if fill is None else fill)
        frame = self._blank_encoded_frames.get(key)
        if frame is None:
            frame = self.encoder.encode(self._get_blank_decoded_frame(size, fill))
            self._blank_encoded_frames[key] = frame
        return frame

    def _get_blank_decoded_frame(
        self, size: Size, fill: int | tuple[int, ...] | None = None
    ) -> np.ndarray:
        """Return the blank frame pixels of a size, cached per size and fill.

        The frame has the level's samples per pixel and the dtype of its bit
        depth. It is shared, so callers must not mutate it.

        Parameters
        ----------
        size: Size
            Size of frame to get.
        fill: int | tuple[int, ...] | None = None
            Value to fill the frame with, or None for the blank color.

        Returns
        ----------
        np.ndarray
            Blank frame as ``(rows, columns)`` for one sample per pixel, otherwise
            ``(rows, columns, samples)``.
        """
        if self._blank_decoded_frames is None:
            self._blank_decoded_frames = {}
        if fill is None:
            fill = self.blank_color
        frame = self._blank_decoded_frames.get((size, fill))
        if frame is None:
            samples = self.samples_per_pixel
            shape = (
                (size.height, size.width)
                if samples == 1
                else (size.height, size.width, samples)
            )
            dtype = np.dtype(np.uint16 if self.bits > 8 else np.uint8)
            frame = np.full(shape, fill, dtype=dtype)
            self._blank_decoded_frames[(size, fill)] = frame
        return frame

    def _detect_blank_tile(
        self, tile: np.ndarray, fill: int | tuple[int, ...] | None = None
    ) -> bool:
        """Detect if tile is a blank tile, i.e. is filled with background color.
        First checks if the corners  before checking whole tile.

        Parameters
        ----------
        tile: np.ndarray
            Tile to check if blank.
        fill: int | tuple[int, ...] | None = None
            Value a blank tile is filled with, or None for the blank color.

        Returns
        ----------
        bool
            True if tile is blank.
        """

        TOP = RIGHT = -1
        BOTTOM = LEFT = 0
        CORNERS_Y = [BOTTOM, BOTTOM, TOP, TOP]
        CORNERS_X = [LEFT, RIGHT, LEFT, RIGHT]
        background = np.array(self.blank_color if fill is None else fill)
        corners_rgb = np.ix_(CORNERS_X, CORNERS_Y)
        return bool(
            np.all(tile[corners_rgb] == background) and np.all(tile == background)
        )


class PixelImageData(BaseDicomizerImageData):
    """ImageData whose source can only produce decoded pixel data.

    The underlying source returns decoded pixels — there are no
    source-encoded bytes to pass through, so producing an encoded tile
    requires re-encoding.

    Subclasses that can read a region more efficiently than wsidicom assembles
    it from tiles override ``get_decoded_region``.

    Every tile is encoded with the encoder, so the transfer syntax and
    photometric interpretation come from it. The defaults are one focal plane,
    one optical path and three samples per pixel; sources with other layouts
    override them.
    """

    def __init__(
        self,
        encoder: Encoder,
        blank_color: int | tuple[int, int, int] | None = None,
    ):
        """Create pixel image data.

        Parameters
        ----------
        encoder: Encoder
            Encoder that encodes every tile.
        blank_color: int | tuple[int, int, int] | None = None
            Background color for empty regions. If None, the default for the
            encoder's photometric interpretation is used.
        """
        super().__init__(encoder)
        if blank_color is None:
            blank_color = self._get_blank_color(encoder.photometric_interpretation)
        self._blank_color = blank_color

    @property
    def transfer_syntax(self) -> UID:
        return self.encoder.transfer_syntax

    @property
    def photometric_interpretation(self) -> str:
        return self.encoder.photometric_interpretation

    @property
    def samples_per_pixel(self) -> int:
        return 3

    @property
    def focal_planes(self) -> list[float]:
        return [0.0]

    @property
    def optical_paths(self) -> list[str]:
        return ["1"]

    @property
    def blank_color(self) -> int | tuple[int, int, int]:
        return self._blank_color

    @property
    def thread_safe(self) -> bool:
        return True

    def _check_z_and_path(self, z: float, path: str) -> None:
        """Raise if `z` or `path` is not available on this image.

        Parameters
        ----------
        z: float
            Focal plane to check.
        path: str
            Optical path to check.

        Raises
        ------
        WsiDicomNotFoundError
            If the focal plane or the optical path is not available.
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))

    def _composite_over_background(self, rgba: np.ndarray) -> np.ndarray:
        """Composite an RGBA array over the background colour, returning RGB.

        Bit-exact with Pillow's paste-with-mask blend
        (``(src * a + bg * (255 - a) + 127) // 255``).

        Parameters
        ----------
        rgba: np.ndarray
            RGBA array to composite.

        Returns
        ----------
        np.ndarray
            RGB array with the alpha composited over the background colour.
        """
        alpha = rgba[..., 3:4].astype(np.int32)
        rgb = rgba[..., :3].astype(np.int32)
        background = np.asarray(self.blank_color, dtype=np.int32)
        composited = (rgb * alpha + background * (255 - alpha) + 127) // 255
        return composited.astype(np.uint8)


class PixelLevelImageData(PixelImageData):
    """A pyramid level of a pixel source, served in tiles of the output tile size.

    Subclasses read the pixels; this holds the level's geometry.
    """

    def __init__(
        self,
        image_size: Size,
        image_metadata: ImageMetadata,
        tile_size: int | None,
        blank_color: int | tuple[int, int, int] | None,
        encoder: Encoder,
        downsample: float = 1.0,
        base_size: Size | None = None,
    ):
        """Create the geometry of a pyramid level.

        Parameters
        ----------
        image_size: Size
            Pixel size of the level.
        image_metadata: ImageMetadata
            Image metadata of the base level, giving its pixel spacing and
            coordinate system.
        tile_size: int | None
            Output tile size. If None, the default tile size is used.
        blank_color: int | tuple[int, int, int] | None
            Background color for empty regions, or None for the encoder's default.
        encoder: Encoder
            Encoder that encodes every tile.
        downsample: float = 1.0
            Downsample of the level relative to the base level.
        base_size: Size | None = None
            Pixel size of the base level, for the imaged size. If None,
            `image_size` is used (the level is the base level).
        """
        super().__init__(encoder, blank_color)
        if tile_size is None:
            tile_size = get_settings().default_tile_size
        self._tile_size = Size(tile_size, tile_size)
        base_pixel_spacing = image_metadata.pixel_spacing
        if base_pixel_spacing is None:
            raise ValueError(
                "Could not determine pixel spacing for the level image: the file did "
                "not provide an mpp that could be read. Give one with the `metadata` "
                "or `default_metadata` argument to convert it anyway."
            )
        self._image_size = image_size
        self._pixel_spacing = SizeMm(
            base_pixel_spacing.width * downsample,
            base_pixel_spacing.height * downsample,
        )
        self._imaged_size = base_pixel_spacing * (base_size or image_size)
        self._image_coordinate_system = image_metadata.image_coordinate_system

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @property
    def pixel_spacing(self) -> SizeMm:
        """Size of the pixels in mm/pixel."""
        return self._pixel_spacing

    @property
    def imaged_size(self) -> SizeMm:
        return self._imaged_size

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem | None:
        return self._image_coordinate_system


class ComposedLevelImageData(PixelLevelImageData):
    """A level composed from stored tiles that overlap.

    The pixels of a region are the placements of the stored tiles under it,
    pasted in tile grid order (row, then column) onto a canvas of the background,
    so the lower and the right-hand tile win an overlap, the same way in every
    region. Each stored tile is decoded once per region,
    even when it is placed several times in it. Subclasses decode the stored
    tiles (`_decode_tile`).
    """

    _TEMPLATE_COUNT = 4
    """Number of region sizes whose filled canvas template is kept."""

    def __init__(
        self,
        overlap: TileOverlap,
        fill: np.ndarray,
        image_metadata: ImageMetadata,
        tile_size: int | None,
        blank_color: int | tuple[int, int, int] | None,
        encoder: Encoder,
    ):
        """Create a composed level.

        Parameters
        ----------
        overlap: TileOverlap
            Placement of the level's stored tiles on the de-overlapped canvas;
            its size is the level's size.
        fill: np.ndarray
            The background as one pixel: a (samples,) array of the tiles' dtype.
        image_metadata: ImageMetadata
            Image metadata of the level, giving its pixel spacing and coordinate
            system.
        tile_size: int | None
            Output tile size. If None, the default tile size is used.
        blank_color: int | tuple[int, int, int] | None
            Background color of blank output tiles, or None for the encoder's
            default.
        encoder: Encoder
            Encoder that encodes every tile.
        """
        super().__init__(
            Size(overlap.image_size.width, overlap.image_size.height),
            image_metadata,
            tile_size,
            blank_color,
            encoder,
        )
        self._overlap_index = OverlapIndex(overlap)
        self._fill = fill
        self._templates = LRU[Size, np.ndarray](self._TEMPLATE_COUNT)

    def get_decoded_region(
        self,
        region: Region,
        z: float,
        path: str,
        *,
        executor: ReadExecutor | None = None,
    ) -> np.ndarray:
        """Compose the pixels of a region.

        Parameters
        ----------
        region: Region
            Pixel region to read.
        z: float
            Z coordinate.
        path: str
            Optical path.
        executor: ReadExecutor | None
            Per-read parallelism the tile decodes fan out across (>1 worker for
            viewing), or None on the conversion path.

        Returns
        -------
        np.ndarray
            The region as a ``(rows, columns, samples)`` array.
        """
        self._check_z_and_path(z, path)
        data = self._compose(region, executor)
        if self._detect_blank_tile(data):
            return self._get_blank_decoded_frame(region.size)
        return data

    def get_decoded_tile(
        self, tile_point: Point, z: float, path: str, cache: bool = True
    ) -> np.ndarray:
        """Return the pixels of a tile.

        Parameters
        ----------
        tile_point: Point
            Tile position to get.
        z: float
            Focal plane of the tile.
        path: str
            Optical path of the tile.
        cache: bool = True
            Unused; decoded stored tiles are cached by the source.

        Returns
        -------
        np.ndarray
            The tile as a ``(rows, columns, samples)`` array.
        """
        return self.get_decoded_region(
            Region(tile_point * self.tile_size, self.tile_size), z, path
        )

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return the encoded bytes of a tile.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        z: float
            Focal plane of the tile.
        path: str
            Optical path of the tile.

        Returns
        -------
        bytes
            The encoded tile.
        """
        self._check_z_and_path(z, path)
        data = self._compose(Region(tile * self.tile_size, self.tile_size))
        if self._detect_blank_tile(data):
            return self._get_blank_encoded_frame(self.tile_size)
        return self.encoder.encode(data)

    @abstractmethod
    def _decode_tile(self, grid_position: OpenTilePoint) -> np.ndarray:
        """Decode the stored tile at a grid position.

        Called from several threads at once when a read is given an executor.

        Parameters
        ----------
        grid_position: OpenTilePoint
            (col, row) of the stored tile, a key of the overlap's placements.

        Returns
        -------
        np.ndarray
            The tile as a (height, width, samples) array of the fill's dtype. It
            is only read from, so it may be shared with a cache.
        """
        raise NotImplementedError()

    def _compose(
        self, region: Region, executor: ReadExecutor | None = None
    ) -> np.ndarray:
        """Compose the placements under a region onto a canvas of the background.

        Parameters
        ----------
        region: Region
            Pixel region to compose.
        executor: ReadExecutor | None = None
            Per-read parallelism the tile decodes fan out across, or None to
            decode serially.

        Returns
        -------
        np.ndarray
            The region as a ``(rows, columns, samples)`` array the caller owns.
        """
        if region.size.width < 0 or region.size.height < 0:
            raise ValueError("Negative size not allowed")
        # the placement works in opentile geometry
        start, size = region.start, region.size
        canvas_region = OpenTileRegion(
            OpenTilePoint(start.x, start.y), OpenTileSize(size.width, size.height)
        )
        placements = self._overlap_index.placements_in(canvas_region)
        # each stored tile once, even when it is placed several times
        tile_positions = list(dict.fromkeys(placement.tile for placement in placements))
        decoded = (
            executor.map(self._decode_tile, tile_positions)
            if executor is not None
            else map(self._decode_tile, tile_positions)
        )
        decoded_tiles = dict(zip(tile_positions, decoded, strict=True))
        canvas = self._blank_canvas(size)
        for placement in placements:
            self._paste(canvas, canvas_region, placement, decoded_tiles[placement.tile])
        return canvas

    @staticmethod
    def _paste(
        canvas: np.ndarray,
        region: OpenTileRegion,
        placement: Placement,
        tile: np.ndarray,
    ) -> None:
        """Paste the placed region of a decoded tile onto a canvas.

        Only the part inside the canvas is pasted.

        Parameters
        ----------
        canvas: np.ndarray
            Destination (height, width[, samples]) array covering `region`;
            pasted into in place.
        region: OpenTileRegion
            Canvas region the destination covers.
        placement: Placement
            Where the tile's placed region goes on the canvas.
        tile: np.ndarray
            The decoded stored tile, with the canvas' samples and dtype.
        """
        canvas_height, canvas_width = canvas.shape[:2]
        left = placement.position.x - region.start.x
        top = placement.position.y - region.start.y
        source = placement.source
        visible_left, visible_top = max(left, 0), max(top, 0)
        visible_right = min(left + source.size.width, canvas_width)
        visible_bottom = min(top + source.size.height, canvas_height)
        if visible_right <= visible_left or visible_bottom <= visible_top:
            return
        source_left = source.start.x + visible_left - left
        source_top = source.start.y + visible_top - top
        canvas[visible_top:visible_bottom, visible_left:visible_right] = tile[
            source_top : source_top + visible_bottom - visible_top,
            source_left : source_left + visible_right - visible_left,
        ]

    def _blank_canvas(self, size: Size) -> np.ndarray:
        """Return a new canvas of a size, filled with the background.

        The canvas is copied from a filled template, which is faster than filling
        a new array each call. Templates for the `_TEMPLATE_COUNT` most recently
        used sizes are kept.

        Parameters
        ----------
        size: Size
            Canvas size in pixels.

        Returns
        -------
        np.ndarray
            A (height, width, samples) canvas the caller owns.
        """
        template = self._templates.get(size)
        if template is None:
            # a lost race only fills one more template
            template = np.empty(
                (size.height, size.width, len(self._fill)), dtype=self._fill.dtype
            )
            template[:] = self._fill  # the fill pixel broadcasts; once per size
            self._templates.put(size, CacheItem(template, 1))
        return template.copy()


class PixelSingleImageData(PixelImageData):
    """A whole decoded image served as one tile, encoded once."""

    def __init__(
        self,
        image: Image,
        blank_color: int | tuple[int, int, int] | None,
        encoder: Encoder,
    ) -> None:
        """Decode and encode an image.

        Parameters
        ----------
        image: Image
            The image. An alpha channel is composited over the blank color.
        blank_color: int | tuple[int, int, int] | None
            Background color, or None for the encoder's default.
        encoder: Encoder
            Encoder that encodes the image.
        """
        super().__init__(encoder, blank_color)
        array = np.asarray(image)
        if array.ndim == 3 and array.shape[2] == 4:
            array = self._composite_over_background(array)
        self._decoded = array
        self._image_size = Size(width=array.shape[1], height=array.shape[0])
        self._encoded_image = self.encoder.encode(array)

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._image_size

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        if tile != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._encoded_image

    def get_decoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str,
        cache: bool = True,
    ) -> np.ndarray:
        if tile_point != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._decoded

    def get_decoded_region(
        self,
        region: Region,
        z: float,
        path: str,
        *,
        executor: ReadExecutor | None = None,
    ) -> np.ndarray:
        left, upper, right, lower = region.box
        return self._decoded[upper:lower, left:right]


class PixelAssociatedImageData(PixelSingleImageData):
    """A label or overview image, without pixel spacing."""

    def __init__(
        self,
        image: Image,
        blank_color: int | tuple[int, int, int] | None,
        encoder: Encoder,
        image_coordinate_system: ImageCoordinateSystem | None = None,
    ) -> None:
        """Create a label or overview image.

        Parameters
        ----------
        image: Image
            The image.
        blank_color: int | tuple[int, int, int] | None
            Background color, or None for the encoder's default.
        encoder: Encoder
            Encoder that encodes the image.
        image_coordinate_system: ImageCoordinateSystem | None = None
            Where the image lies on the slide, if known.
        """
        super().__init__(image, blank_color, encoder)
        self._image_coordinate_system = image_coordinate_system

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem | None:
        return self._image_coordinate_system

    @property
    def pixel_spacing(self) -> SizeMm | None:
        """Size of the pixels in mm/pixel."""
        return None

    @property
    def imaged_size(self) -> SizeMm | None:
        return None


class PixelThumbnailImageData(PixelSingleImageData):
    """A thumbnail of the base level, cropped to the region the pyramid covers."""

    def __init__(
        self,
        image: Image,
        blank_color: int | tuple[int, int, int] | None,
        offset: Point | None,
        size: Size | None,
        base_size: Size,
        image_metadata: ImageMetadata,
        encoder: Encoder,
    ) -> None:
        """Crop a thumbnail to the pyramid's region.

        Parameters
        ----------
        image: Image
            The thumbnail, covering `base_size` base-level pixels.
        blank_color: int | tuple[int, int, int] | None
            Background color, or None for the encoder's default.
        offset: Point | None
            Base-level position of the pyramid's region in the thumbnail's
            extent, or None for the top-left corner.
        size: Size | None
            Base-level size of the pyramid's region, or None for the rest of the
            thumbnail from `offset`.
        base_size: Size
            Base-level pixel size the whole thumbnail covers.
        image_metadata: ImageMetadata
            Image metadata of the base level, giving its pixel spacing and
            coordinate system.
        encoder: Encoder
            Encoder that encodes the image.
        """
        self._image_coordinate_system = image_metadata.image_coordinate_system
        if image_metadata.pixel_spacing is None:
            raise ValueError(
                "Could not determine pixel spacing for the thumbnail image: the file "
                "did not provide an mpp that could be read. Give one with the "
                "`metadata` or `default_metadata` argument to convert it anyway."
            )
        downsample = base_size.width / image.width
        self._pixel_spacing = SizeMm(
            image_metadata.pixel_spacing.width * downsample,
            image_metadata.pixel_spacing.height * downsample,
        )

        if offset is not None:
            crop_offset = Point(
                round(offset.x / downsample), round(offset.y / downsample)
            )
        else:
            crop_offset = Point(0, 0)
        if size is not None:
            crop_size = Size(
                round(size.width / downsample), round(size.height / downsample)
            )
            self._imaged_size = image_metadata.pixel_spacing * size
        else:
            crop_size = Size.from_tuple(image.size) - crop_offset
            self._imaged_size = image_metadata.pixel_spacing * base_size

        cropped = image.crop(
            (
                crop_offset.x,
                crop_offset.y,
                crop_offset.x + crop_size.width,
                crop_offset.y + crop_size.height,
            )
        )
        super().__init__(cropped, blank_color, encoder)

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem | None:
        return self._image_coordinate_system

    @property
    def pixel_spacing(self) -> SizeMm:
        """Size of the pixels in mm/pixel."""
        return self._pixel_spacing

    @property
    def imaged_size(self) -> SizeMm:
        return self._imaged_size
