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
from typing import List, Optional, Sequence

from tiffslide import TiffSlide

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.encoding import Encoder
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.metadata import WsiMetadata
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
        tile_size: int = 512,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        **source_args,
    ) -> None:
        self._tiffslide = TiffSlide(filepath, **source_args)
        self._image_metadata = TiffSlideMetadata(self._tiffslide)
        self._pyramid_levels = [
            int(round(math.log2(downsample)))
            for downsample in self._tiffslide.level_downsamples
        ]
        super().__init__(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_levels,
            include_label,
            include_overview,
            include_confidential,
        )

    def close(self):
        self._tiffslide.close()

    @property
    def has_label(self) -> bool:
        return "label" in self._tiffslide.associated_images

    @property
    def has_overview(self) -> bool:
        return "macro" in self._tiffslide.associated_images

    @property
    def image_metadata(self) -> WsiMetadata:
        return self._image_metadata

    @property
    def pyramid_levels(self) -> List[int]:
        return self._pyramid_levels

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by TiffSlide."""
        format = TiffSlide.detect_format(filepath)
        return format is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        return TiffSlideLevelImageData(
            self._tiffslide, level_index, self._tile_size, self._encoder
        )

    def _create_label_image_data(self) -> DicomizerImageData:
        return TiffSlideAssociatedImageData(
            self._tiffslide, TiffSlideAssociatedImageType.LABEL, self._encoder
        )

    def _create_overview_image_data(self) -> DicomizerImageData:
        return TiffSlideAssociatedImageData(
            self._tiffslide, TiffSlideAssociatedImageType.MACRO, self._encoder
        )
