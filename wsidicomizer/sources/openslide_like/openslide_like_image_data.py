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

from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image as Pillow
from PIL.Image import Image
from pydicom.uid import UID
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem

from wsidicomizer.config import settings
from wsidicomizer.image_data import DicomizerImageData


class OpenSlideLikeImageData(DicomizerImageData):
    def __init__(
        self,
        blank_color: Optional[Union[int, Tuple[int, int, int]]],
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
    def focal_planes(self) -> List[float]:
        return [0.0]

    @property
    def optical_paths(self) -> List[str]:
        return ["0"]

    @property
    def blank_color(self) -> Union[int, Tuple[int, int, int]]:
        return self._blank_color

    @property
    def thread_safe(self) -> bool:
        return True

    def _remove_alpha(self, alpha_image: Image) -> Image:
        """Remove alpha channel from image.

        Parameters
        ----------
        alpha_image: Image
            Image to remove alpha from.

        Returns
        ----------
        Image
            Image without alpha channel.
        """
        image = Pillow.new("RGB", alpha_image.size, self.blank_color)
        image.paste(alpha_image, mask=alpha_image.split()[3])
        return image


class OpenSlideLikeSingleImageData(OpenSlideLikeImageData):
    def __init__(
        self,
        image: Image,
        blank_color: Optional[Union[int, Tuple[int, int, int]]],
        encoder: Encoder,
    ) -> None:
        super().__init__(
            blank_color,
            encoder,
        )
        if image.mode == "RGBA":
            image = self._remove_alpha(image)
        self._image_size = Size.from_tuple(image.size)
        self._decoded_image = image
        self._encoded_image = self.encoder.encode(np.asarray(image))
        self._image_size = Size.from_tuple(image.size)

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._image_size

    def _get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        if tile != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._encoded_image

    def _get_decoded_tile(self, tile: Point, z: float, path: str) -> Image:
        if tile != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._decoded_image


class OpenSlideLikeAssociatedImageData(OpenSlideLikeSingleImageData):
    @property
    def pixel_spacing(self) -> Optional[SizeMm]:
        """Size of the pixels in mm/pixel."""
        return None

    @property
    def imaged_size(self) -> Optional[Size]:
        return None


class OpenSlideLikeThumbnailImageData(OpenSlideLikeSingleImageData):
    def __init__(
        self,
        image: Image,
        blank_color: Optional[Union[int, Tuple[int, int, int]]],
        offset: Optional[Point],
        size: Optional[Size],
        level_dimensions: Sequence[Tuple[int, int]],
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
        self._imaged_size = image_metadata.pixel_spacing * Size.from_tuple(
            base_level_dimensions
        )
        if offset is not None:
            offset = Point(round(offset.x / downsample), round(offset.y / downsample))
        else:
            offset = Point(0, 0)
        if size is not None:
            size = Size(round(size.width / downsample), round(size.height / downsample))
        else:
            size = Size.from_tuple(image.size) - offset
        cropped = image.crop(
            (offset.x, offset.y, offset.x + size.width, offset.y + size.height)
        )
        super().__init__(
            cropped,
            blank_color,
            encoder,
        )

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        if self._image_coordinate_system is None:
            return super().image_coordinate_system
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
        blank_color: Optional[Union[int, Tuple[int, int, int]]],
        offset: Optional[Point],
        size: Optional[Size],
        level_dimensions: Sequence[Tuple[int, int]],
        level_downsamples: Sequence[float],
        image_metadata: ImageMetadata,
        level_index: int,
        tile_size: Optional[int],
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
        self._image_size = Size.from_tuple(level_dimensions[self._level_index])
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
        else:
            self._image_size = Size.from_tuple(level_dimensions[self._level_index])

        self._blank_encoded_frame = bytes()
        self._blank_encoded_frame_size = None
        self._blank_decoded_frame = None
        self._blank_decoded_frame_size = None
        self._image_coordinate_system = image_metadata.image_coordinate_system
        self._imaged_size = image_metadata.pixel_spacing * Size.from_tuple(
            level_dimensions[0]
        )

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
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        if self._image_coordinate_system is None:
            return super().image_coordinate_system
        return self._image_coordinate_system
