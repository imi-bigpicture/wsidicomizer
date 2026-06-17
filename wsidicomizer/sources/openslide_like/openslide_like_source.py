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

"""Source for reading openslide like compatible file."""

import math
import re
from collections.abc import Mapping, Sequence
from enum import Enum
from pathlib import Path

from PIL.Image import Image
from pydicom import Dataset
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Size
from wsidicom.metadata import UidGenerator, WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor, WsiDicomizerMetadata
from wsidicomizer.pixel_wsi_instance import PixelWsiInstance
from wsidicomizer.sources.openslide_like import (
    OpenSlideLikeAssociatedImageData,
    OpenSlideLikeProperties,
    OpenSlideLikeThumbnailImageData,
)
from wsidicomizer.sources.openslide_like.openslide_like_metadata import (
    OpenSlideLikeMetadata,
)


class OpenSlideLikeAssociatedImageType(Enum):
    LABEL = "label"
    MACRO = "macro"
    THUMBNAIL = "thumbnail"


class OpenSlideLikeSource(DicomizerSource):
    _instance_cls = PixelWsiInstance

    def __init__(
        self,
        filepath: Path,
        properties: OpenSlideLikeProperties,
        level_downsamples: Sequence[float],
        level_dimensions: Sequence[tuple[int, int]],
        associated_images: Mapping[str, Image],
        base_metadata: OpenSlideLikeMetadata,
        encoder: Encoder,
        tile_size: int | None = None,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        uid_generator: UidGenerator | None = None,
    ) -> None:
        """Create a new OpenSlideLikeSource.

        Parameters
        ----------
        filepath: Path
            Path to the file.
        properties: OpenSlideLikeProperties
            Properties of the file.
        level_downsamples: Sequence[float]
            Downsamples of the levels.
        level_dimensions: Sequence[Tuple[int, int]]
            Dimensions of the levels.
        associated_images: Mapping[str, Image]
            Associated images in the file.
        base_metadata: OpenSlideLikeMetadata
            Base metadata for the file.
        encoder: Encoder
            Encoder to use. Pyramid is always re-encoded using the encoder.
        tile_size: Optional[int] = None,
            Tile size to use. If None, the default tile size is used.
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        include_confidential: bool = True
            Include confidential metadata.
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None
            Optional metadata post processing by update from dataset or callback.

        """
        self._base_metadata = base_metadata
        self._level_downsamples = level_downsamples
        self._level_dimensions = level_dimensions
        self._associated_images = associated_images
        self._pyramid_levels = {
            (int(round(math.log2(downsample))), 0.0, "0"): index
            for index, downsample in enumerate(level_downsamples)
        }

        self._blank_color = self._get_blank_color(properties)
        self._base_level_offset, self._base_level_size = self._get_offset_and_size(
            properties
        )
        super().__init__(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            metadata_post_processor,
            uid_generator,
        )

    @property
    def base_metadata(self) -> WsiDicomizerMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> dict[tuple[int, float, str], int]:
        return self._pyramid_levels

    def _create_label_image_data(self) -> BaseDicomizerImageData | None:
        label_image = self._get_associated_image(OpenSlideLikeAssociatedImageType.LABEL)
        if label_image is None:
            return None
        label_image_coordinate_system = None
        if self.metadata.label and self.metadata.label.image:
            label_image_coordinate_system = (
                self.metadata.label.image.image_coordinate_system
            )
        return OpenSlideLikeAssociatedImageData(
            label_image,
            self._blank_color,
            self._encoder,
            image_coordinate_system=label_image_coordinate_system,
        )

    def _create_overview_image_data(self) -> BaseDicomizerImageData | None:
        overview_image = self._get_associated_image(
            OpenSlideLikeAssociatedImageType.MACRO
        )
        if overview_image is None:
            return None
        overview_image_coordinate_system = None
        if self.metadata.overview and self.metadata.overview.image:
            overview_image_coordinate_system = (
                self.metadata.overview.image.image_coordinate_system
            )
        return OpenSlideLikeAssociatedImageData(
            overview_image,
            self._blank_color,
            self._encoder,
            image_coordinate_system=overview_image_coordinate_system,
        )

    def _create_thumbnail_image_data(self) -> BaseDicomizerImageData | None:
        label_image = self._get_associated_image(
            OpenSlideLikeAssociatedImageType.THUMBNAIL
        )
        if label_image is None:
            return None
        return OpenSlideLikeThumbnailImageData(
            label_image,
            self._blank_color,
            self._base_level_offset,
            self._base_level_size,
            self._level_dimensions,
            self.metadata.pyramid.image,
            self._encoder,
        )

    def _get_associated_image(
        self, image_type: OpenSlideLikeAssociatedImageType
    ) -> Image | None:
        """Get image from associated images.

        Parameters
        ----------
        associated_images: Mapping[str, Image]
            Associated images to get image from.
        image_type: str
            Type of image to get.

        Returns
        ----------
        Image
            Associated image.
        """
        return self._associated_images.get(image_type.value)

    @staticmethod
    def _get_blank_color(
        properties: OpenSlideLikeProperties,
    ) -> int | tuple[int, int, int] | None:
        if properties.background_color is not None:
            rgb = re.findall(r"([0-9a-fA-F]{2})", properties.background_color)
            if len(rgb) == 3:
                return (int(rgb[0], 16), int(rgb[1], 16), int(rgb[2], 16))
        return None

    @staticmethod
    def _get_offset_and_size(
        properties: OpenSlideLikeProperties,
    ) -> tuple[Point | None, Size | None]:
        if properties.bounds_x is not None and properties.bounds_y is not None:
            offset = Point(int(properties.bounds_x), int(properties.bounds_y))
        else:
            offset = None
        if properties.bounds_width is not None and properties.bounds_height is not None:
            size = Size(int(properties.bounds_width), int(properties.bounds_height))
        else:
            size = None
        return offset, size
