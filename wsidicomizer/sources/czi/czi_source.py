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

"""Source for reading czi file."""

from pathlib import Path
from typing import List, Optional

from czifile import CziFile
from wsidicom.codec import Encoder
from wsidicom.metadata import WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.sources.czi.czi_image_data import CziImageData
from wsidicomizer.sources.czi.czi_metadata import CziMetadata


class CziSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: int = 512,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_confidential: bool = True,
    ) -> None:
        super().__init__(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
        )
        self._czi = CziFile(filepath)
        self._base_metadata = CziMetadata(self._czi)

    def close(self) -> None:
        return self._czi.close()

    @property
    def has_label(self) -> bool:
        return False

    @property
    def has_overview(self) -> bool:
        return False

    @property
    def pyramid_levels(self) -> List[int]:
        return [0]

    @property
    def base_metadata(self) -> CziMetadata:
        return self._base_metadata

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by CziFile."""
        return CziImageData.detect_format(filepath) is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        if level_index != 0:
            raise ValueError()  # TODO
        return CziImageData(
            self._czi,
            self._tile_size,
            self._encoder,
            self.base_metadata,
            self.metadata.image,
        )

    def _create_label_image_data(self) -> DicomizerImageData:
        return super()._create_label_image_data()

    def _create_overview_image_data(self) -> DicomizerImageData:
        return super()._create_overview_image_data()
