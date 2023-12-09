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

"""Source for reading opentile compatible file."""

from pathlib import Path
from typing import List, Optional, Sequence, Union

from opentile import OpenTile
from opentile.metadata import Metadata
from pydicom import Dataset
from wsidicom.codec import Encoder

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.sources.opentile.opentile_image_data import OpenTileImageData


class OpenTileSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: int = 512,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        include_confidential: bool = True,
        force_transcoding: bool = False,
    ) -> None:
        self._tiler = OpenTile.open(filepath, tile_size)
        self._metadata = self._tiler.metadata
        self._force_transcoding = force_transcoding
        super().__init__(
            filepath,
            encoder,
            tile_size,
            modules,
            include_confidential,
        )

    def close(self):
        self._tiler.close()

    @property
    def has_label(self) -> bool:
        return len(self._tiler.labels) > 0

    @property
    def has_overview(self) -> bool:
        return len(self._tiler.overviews) > 0

    @property
    def metadata(self) -> Metadata:
        return self._metadata

    @property
    def pyramid_levels(self) -> List[int]:
        return [level.pyramid_index for level in self._tiler.levels]

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by OpenTile."""
        return OpenTile.detect_format(filepath) is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        level = self._tiler.levels[level_index]
        return OpenTileImageData(
            level, self._encoder, self.metadata.image_offset, self._force_transcoding
        )

    def _create_label_image_data(self) -> DicomizerImageData:
        label = self._tiler.labels[0]
        return OpenTileImageData(
            label, self._encoder, force_transcoding=self._force_transcoding
        )

    def _create_overview_image_data(self) -> DicomizerImageData:
        overview = self._tiler.overviews[0]
        return OpenTileImageData(
            overview, self._encoder, force_transcoding=self._force_transcoding
        )
