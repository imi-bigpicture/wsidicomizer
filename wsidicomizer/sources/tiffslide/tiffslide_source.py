#    Copyright 2023 SECTRA AB

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

"""Source for reading tiffslide compatible file."""

import math
from pathlib import Path
from typing import Dict, Optional

from tiffslide import TiffSlide
from wsidicom.codec import Encoder
from wsidicom.metadata import WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.sources.tiffslide.tiffslide_image_data import (
    TiffSlideAssociatedImageData,
    TiffSlideAssociatedImageType,
    TiffSlideLevelImageData,
)
from wsidicomizer.sources.tiffslide.tiffslide_metadata import TiffSlideMetadata


class TiffSlideSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: Optional[int] = None,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_confidential: bool = True,
        **source_args,
    ) -> None:
        self._tiffslide = TiffSlide(filepath, **source_args)
        self._base_metadata = TiffSlideMetadata(self._tiffslide)
        self._pyramid_levels = {
            int(round(math.log2(downsample))): index
            for index, downsample in enumerate(self._tiffslide.level_downsamples)
        }
        super().__init__(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
        )

    def close(self):
        self._tiffslide.close()

    @property
    def base_metadata(self) -> WsiMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> Dict[int, int]:
        return self._pyramid_levels

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by TiffSlide."""
        format = TiffSlide.detect_format(filepath)
        return format is not None

    def _create_level_image_data(
        self, level_index: int
    ) -> Optional[DicomizerImageData]:
        return TiffSlideLevelImageData(
            self._tiffslide,
            self.metadata.image,
            level_index,
            self._tile_size,
            self._encoder,
        )

    def _create_label_image_data(self) -> Optional[DicomizerImageData]:
        if (
            TiffSlideAssociatedImageType.LABEL.value
            not in self._tiffslide.associated_images
        ):
            return None
        return TiffSlideAssociatedImageData(
            self._tiffslide, TiffSlideAssociatedImageType.LABEL, self._encoder
        )

    def _create_overview_image_data(self) -> Optional[DicomizerImageData]:
        if (
            TiffSlideAssociatedImageType.MACRO.value
            not in self._tiffslide.associated_images
        ):
            return None
        return TiffSlideAssociatedImageData(
            self._tiffslide, TiffSlideAssociatedImageType.MACRO, self._encoder
        )

    def _create_thumbnail_image_data(self) -> Optional[DicomizerImageData]:
        if (
            TiffSlideAssociatedImageType.THUMBNAIL.value
            not in self._tiffslide.associated_images
        ):
            return None
        return TiffSlideAssociatedImageData(
            self._tiffslide, TiffSlideAssociatedImageType.THUMBNAIL, self._encoder
        )
