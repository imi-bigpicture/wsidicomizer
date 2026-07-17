#    Copyright 2025 SECTRA AB
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

from collections.abc import Sequence

import numpy as np
from PIL.Image import Image
from pydicom.uid import UID
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem

from wsidicomizer.config import settings
from wsidicomizer.image_data import PixelImageData


class OpenSlideLikeImageData(PixelImageData):
    def __init__(
        self,
        blank_color: int | tuple[int, int, int] | None,
        encoder: Encoder,
    ):
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


class OpenSlideLikeSingleImageData(OpenSlideLikeImageData):
    def __init__(
        self,
        image: Image,
        blank_color: int | tuple[int, int, int] | None,
        encoder: Encoder,
    ) -> None:
        super().__init__(
            blank_color,
            encoder,
        )
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

    def read_region(self, region: Region, z: float, path: str) -> np.ndarray:
        left, upper, right, lower = region.box
        return self._decoded[upper:lower, left:right]


class OpenSlideLikeAssociatedImageData(OpenSlideLikeSingleImageData):
    def __init__(
        self,
        image: Image,
        blank_color: int | tuple[int, int, int] | None,
        encoder: Encoder,
        image_coordinate_system: ImageCoordinateSystem | None = None,
    ) -> None:
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


class OpenSlideLikeThumbnailImageData(OpenSlideLikeSingleImageData):
    def __init__(
        self,
        image: Image,
        blank_color: int | tuple[int, int, int] | None,
        offset: Point | None,
        size: Size | None,
        level_dimensions: Sequence[tuple[int, int]],
        image_metadata: ImageMetadata,
        encoder: Encoder,
    ) -> None:
        self._image_coordinate_system = image_metadata.image_coordinate_system
        if image_metadata.pixel_spacing is None:
            raise ValueError(
                "Could not determine pixel spacing for openslide thumbnail image."
            )
        base_level_dimensions = level_dimensions[0]
        downsample = (
            SizeMm.from_tuple(base_level_dimensions).width
            / Size.from_tuple(image.size).width
        )
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
            self._imaged_size = image_metadata.pixel_spacing * Size.from_tuple(
                base_level_dimensions
            )

        cropped = image.crop(
            (
                crop_offset.x,
                crop_offset.y,
                crop_offset.x + crop_size.width,
                crop_offset.y + crop_size.height,
            )
        )
        super().__init__(
            cropped,
            blank_color,
            encoder,
        )

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


class OpenSlideLikeLevelImageData(OpenSlideLikeImageData):
    def __init__(
        self,
        blank_color: int | tuple[int, int, int] | None,
        offset: Point | None,
        size: Size | None,
        level_dimensions: Sequence[tuple[int, int]],
        level_downsamples: Sequence[float],
        image_metadata: ImageMetadata,
        level_index: int,
        tile_size: int | None,
        encoder: Encoder,
    ):
        super().__init__(
            blank_color,
            encoder,
        )
        if tile_size is None:
            tile_size = settings.default_tile_size
        self._tile_size = Size(tile_size, tile_size)
        self._level_index = level_index
        self._downsample = level_downsamples[self._level_index]
        if image_metadata.pixel_spacing is None:
            raise ValueError(
                "Could not determine pixel spacing for tiffslide level image."
            )
        self._pixel_spacing = SizeMm(
            image_metadata.pixel_spacing.width * self._downsample,
            image_metadata.pixel_spacing.height * self._downsample,
        )

        self._offset = offset or Point(0, 0)

        if size is not None:
            self._image_size = size // int(round(self._downsample))
            self._imaged_size = image_metadata.pixel_spacing * size
        else:
            self._image_size = Size.from_tuple(level_dimensions[self._level_index])
            self._imaged_size = image_metadata.pixel_spacing * Size.from_tuple(
                level_dimensions[0]
            )

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
