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

"""Source for reading openslide compatible file."""

import math
from pathlib import Path
from typing import Dict, Optional, Union

from pydicom import Dataset
from wsidicom.codec import Encoder
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.extras.openslide.openslide import OpenSlide
from wsidicomizer.extras.openslide.openslide_image_data import (
    OpenSlideAssociatedImageData,
    OpenSlideAssociatedImageType,
    OpenSlideLevelImageData,
    OpenSlideThumbnailImageData,
)
from wsidicomizer.extras.openslide.openslide_metadata import OpenSlideMetadata
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor


class OpenSlideSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: Optional[int] = None,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_confidential: bool = True,
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None,
    ) -> None:
        """Create a new OpenSlideSource.

        Parameters
        ----------
        filepath: Path
            Path to the file.
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
        self._slide = OpenSlide(filepath)

        self._pyramid_levels = self._get_pyramid_levels(self._slide)
        self._base_metadata = OpenSlideMetadata(self._slide)
        super().__init__(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            metadata_post_processor,
        )

    def close(self) -> None:
        return self._slide.close()

    @property
    def base_metadata(self) -> WsiMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> Dict[int, int]:
        return self._pyramid_levels

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by OpenSlide."""
        return OpenSlide.detect_format(str(filepath)) is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        return OpenSlideLevelImageData(
            self._slide,
            self.metadata.image,
            level_index,
            self._tile_size,
            self._encoder,
        )

    def _create_label_image_data(self) -> Optional[DicomizerImageData]:
        if (
            OpenSlideAssociatedImageType.LABEL.value
            not in self._slide.associated_images
        ):
            return None
        return OpenSlideAssociatedImageData(
            self._slide, OpenSlideAssociatedImageType.LABEL, self._encoder
        )

    def _create_overview_image_data(self) -> Optional[DicomizerImageData]:
        if (
            OpenSlideAssociatedImageType.MACRO.value
            not in self._slide.associated_images
        ):
            return None
        return OpenSlideAssociatedImageData(
            self._slide, OpenSlideAssociatedImageType.MACRO, self._encoder
        )

    def _create_thumbnail_image_data(self) -> Optional[DicomizerImageData]:
        if (
            OpenSlideAssociatedImageType.THUMBNAIL.value
            not in self._slide.associated_images
        ):
            return None
        return OpenSlideThumbnailImageData(
            self._slide, self.metadata.image, self._encoder
        )

    @staticmethod
    def _get_pyramid_levels(slide: OpenSlide) -> Dict[int, int]:
        """Return list of pyramid levels present in openslide slide."""
        return {
            int(math.log2(int(downsample))): index
            for index, downsample in enumerate(slide.level_downsamples)
        }
