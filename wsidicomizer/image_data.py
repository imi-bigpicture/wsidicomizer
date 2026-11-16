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
from PIL.Image import Image
from pydicom.uid import UID
from wsidicom import ImageData
from wsidicom.codec import Encoder
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem, LossyCompression

from wsidicomizer.config import get_settings


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

    Concrete subclasses implement ``read_region`` either as a native call
    (for pyramidal/tiled sources) or as an in-memory crop of a pre-decoded
    image (for single-image label/overview/thumbnail sources). Pair with
    ``PixelWsiInstance`` so reads route through ``read_region`` instead of
    per-tile stitching.

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

    @abstractmethod
    def read_region(self, region: Region, z: float, path: str) -> np.ndarray:
        """Read the pixels of a region from the source.

        The region-read primitive. Pixel sources decode to numpy and implement
        this; Pillow, when needed, is derived at the read boundary.

        Parameters
        ----------
        region: Region
            Pixel region to read.
        z: float
            Z coordinate.
        path: str
            Optical path.

        Returns
        -------
        np.ndarray
            The region as ``(rows, columns)`` or ``(rows, columns, samples)``.
        """
        raise NotImplementedError()

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

    def read_region(
        self, region: Region, z: float, path: str, executor: ReadExecutor | None = None
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
