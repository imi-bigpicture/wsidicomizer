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
        from wsidicomizer.config import settings
        
        # Store tile_size for use in associated image filtering
        self._tile_size = tile_size
        
        self._base_metadata = base_metadata
        self._level_downsamples = level_downsamples
        self._level_dimensions = level_dimensions
        self._associated_images = associated_images
        
        # Determine actual tile size to use for filtering
        actual_tile_size = tile_size if tile_size is not None else settings.default_tile_size
        
        # Filter out levels where width or height is smaller than tile size
        self._pyramid_levels = {
            (int(round(math.log2(downsample))), 0.0, "0"): index
            for index, downsample in enumerate(level_downsamples)
            if (level_dimensions[index][0] >= actual_tile_size and 
                level_dimensions[index][1] >= actual_tile_size)
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
        
        # Check if label image is too small compared to tile size
        from wsidicomizer.config import settings
        actual_tile_size = self._tile_size if self._tile_size is not None else settings.default_tile_size
        label_width, label_height = label_image.size
        
        if label_width < actual_tile_size or label_height < actual_tile_size:
            # Skip label if it's smaller than tile size
            return None
        
        # Calculate downsample factor for accurate pixel spacing
        base_pixel_spacing = self.base_metadata.image.pixel_spacing
        downsample_factor = None
        
        if base_pixel_spacing is not None and len(self._level_dimensions) > 0:
            base_width, base_height = self._level_dimensions[0]
            
            # Calculate downsample factor based on width ratio
            downsample_factor = base_width / label_width
        
        return OpenSlideLikeAssociatedImageData(
            label_image,
            self._blank_color,
            self._encoder,
            base_pixel_spacing,
            downsample_factor,
        )

    def _create_overview_image_data(self) -> Optional[DicomizerImageData]:
        overview_image = self._get_associated_image(
            OpenSlideLikeAssociatedImageType.MACRO
        )
        if overview_image is None:
            return None
        
        # Check if overview image is too small compared to tile size
        from wsidicomizer.config import settings
        actual_tile_size = self._tile_size if self._tile_size is not None else settings.default_tile_size
        overview_width, overview_height = overview_image.size
        
        if overview_width < actual_tile_size or overview_height < actual_tile_size:
            # Skip overview if it's smaller than tile size
            return None
        
        # Calculate downsample factor for accurate pixel spacing
        base_pixel_spacing = self.base_metadata.image.pixel_spacing
        downsample_factor = None
        
        if base_pixel_spacing is not None and len(self._level_dimensions) > 0:
            base_width, base_height = self._level_dimensions[0]
            
            # Calculate downsample factor based on width ratio
            downsample_factor = base_width / overview_width
        
        return OpenSlideLikeAssociatedImageData(
            overview_image,
            self._blank_color,
            self._encoder,
            base_pixel_spacing,
            downsample_factor,
        )

    def _create_thumbnail_image_data(self) -> Optional[DicomizerImageData]:
        thumbnail_image = self._get_associated_image(
            OpenSlideLikeAssociatedImageType.THUMBNAIL
        )
        if thumbnail_image is None:
            return None
        
        # Create the thumbnail data first to get the final cropped size
        thumbnail_data = OpenSlideLikeThumbnailImageData(
            thumbnail_image,
            self._blank_color,
            self._base_level_offset,
            self._base_level_size,
            self._level_dimensions,
            self.metadata.image,
            self._encoder,
        )
        
        # Filter thumbnails smaller than tile size AFTER cropping
        from wsidicomizer.config import settings
        actual_tile_size = self._tile_size or settings.default_tile_size
        final_width, final_height = thumbnail_data.image_size.width, thumbnail_data.image_size.height
        if final_width < actual_tile_size or final_height < actual_tile_size:
            return None
        
        return thumbnail_data

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
