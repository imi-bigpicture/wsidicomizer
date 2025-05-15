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
from enum import Enum
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple, Union

from PIL.Image import Image
from pydicom import Dataset
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Size
from wsidicom.metadata import WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor
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
    def __init__(
        self,
        filepath: Path,
        properties: OpenSlideLikeProperties,
        level_downsamples: Sequence[float],
        level_dimensions: Sequence[Tuple[int, int]],
        associated_images: Mapping[str, Image],
        base_metadata: OpenSlideLikeMetadata,
        encoder: Encoder,
        tile_size: Optional[int] = None,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_confidential: bool = True,
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None,
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
        )

    @property
    def base_metadata(self) -> WsiMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> Dict[Tuple[int, float, str], int]:
        return self._pyramid_levels

    def _create_label_image_data(self) -> Optional[DicomizerImageData]:
        label_image = self._get_associated_image(OpenSlideLikeAssociatedImageType.LABEL)
        if label_image is None:
            return None
        return OpenSlideLikeAssociatedImageData(
            label_image,
            self._blank_color,
            self._encoder,
        )

    def _create_overview_image_data(self) -> Optional[DicomizerImageData]:
        overview_image = self._get_associated_image(
            OpenSlideLikeAssociatedImageType.MACRO
        )
        if overview_image is None:
            return None
        return OpenSlideLikeAssociatedImageData(
            overview_image,
            self._blank_color,
            self._encoder,
        )

    def _create_thumbnail_image_data(self) -> Optional[DicomizerImageData]:
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
            self.metadata.image,
            self._encoder,
        )

    def _get_associated_image(
        self, image_type: OpenSlideLikeAssociatedImageType
    ) -> Optional[Image]:
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
    ) -> Optional[Union[int, Tuple[int, int, int]]]:
        if properties.background_color is not None:
            rgb = re.findall(r"([0-9a-fA-F]{2})", properties.background_color)
            if len(rgb) == 3:
                return (int(rgb[0], 16), int(rgb[1], 16), int(rgb[2], 16))
        return None

    @staticmethod
    def _get_offset_and_size(
        properties: OpenSlideLikeProperties,
    ) -> Tuple[Optional[Point], Optional[Size]]:
        if properties.bounds_x is not None and properties.bounds_y is not None:
            offset = Point(int(properties.bounds_x), int(properties.bounds_y))
        else:
            offset = None
        if properties.bounds_width is not None and properties.bounds_height is not None:
            size = Size(int(properties.bounds_width), int(properties.bounds_height))
        else:
            size = None
        return offset, size
