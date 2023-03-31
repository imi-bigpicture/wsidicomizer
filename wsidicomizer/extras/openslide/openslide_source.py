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
from typing import List, Optional, Sequence, Union

from opentile.metadata import Metadata
from pydicom import Dataset

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.encoding import Encoder
from wsidicomizer.extras.openslide.openslide import OpenSlide
from wsidicomizer.extras.openslide.openslide_image_data import (
    OpenSlideAssociatedImageData,
    OpenSlideAssociatedImageType,
    OpenSlideLevelImageData,
)
from wsidicomizer.extras.openslide.openslide_metadata import OpenSlideMetadata
from wsidicomizer.image_data import DicomizerImageData


class OpenSlideSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: int = 512,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
    ) -> None:
        self._slide = OpenSlide(filepath)
        self._pyramid_levels = self._get_pyramid_levels(self._slide)
        self._metadata = OpenSlideMetadata(self._slide)
        super().__init__(
            filepath,
            encoder,
            tile_size,
            modules,
            include_levels,
            include_label,
            include_overview,
            include_confidential,
        )

    def close(self) -> None:
        return self._slide.close()

    @property
    def has_label(self) -> bool:
        return OpenSlideAssociatedImageType.LABEL.value in self._slide.associated_images

    @property
    def has_overview(self) -> bool:
        return OpenSlideAssociatedImageType.MACRO.value in self._slide.associated_images

    @property
    def metadata(self) -> Metadata:
        return self._metadata

    @property
    def pyramid_levels(self) -> List[int]:
        return self._pyramid_levels

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by OpenSlide."""
        return OpenSlide.detect_format(str(filepath)) is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        return OpenSlideLevelImageData(
            self._slide, level_index, self._tile_size, self._encoder
        )

    def _create_label_image_data(self) -> DicomizerImageData:
        return OpenSlideAssociatedImageData(
            self._slide, OpenSlideAssociatedImageType.LABEL, self._encoder
        )

    def _create_overview_image_data(self) -> DicomizerImageData:
        return OpenSlideAssociatedImageData(
            self._slide, OpenSlideAssociatedImageType.MACRO, self._encoder
        )

    @staticmethod
    def _get_pyramid_levels(slide: OpenSlide) -> List[int]:
        """Return list of pyramid levels present in openslide slide."""
        return [
            int(math.log2(int(downsample))) for downsample in slide.level_downsamples
        ]
