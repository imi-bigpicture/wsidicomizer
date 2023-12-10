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

"""Source using bioformats."""

from pathlib import Path
from typing import List, Optional, Tuple

from wsidicom.codec import Encoder
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.extras.bioformats.bioformats_image_data import BioformatsImageData
from wsidicomizer.extras.bioformats.bioformats_reader import BioformatsReader
from wsidicomizer.image_data import DicomizerImageData


class BioformatsSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: Optional[int] = None,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_confidential: bool = True,
        readers: Optional[int] = None,
        cache_path: Optional[str] = None,
    ) -> None:
        if tile_size is None:
            raise ValueError("Tile size required for bioformats")
        self._reader = BioformatsReader(Path(filepath), readers, cache_path)
        (
            self._pyramid_image_index,
            self._label_image_index,
            self._overview_image_index,
        ) = self._get_image_indices(self._reader)
        super().__init__(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
        )

    @property
    def has_label(self) -> bool:
        return self._label_image_index is not None

    @property
    def has_overview(self) -> bool:
        return self._overview_image_index is not None

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by Bio-Formats."""
        return BioformatsImageData.detect_format(filepath)

    @property
    def pyramid_levels(self) -> List[int]:
        """Return pyramid levels (scalings) for file."""
        return list(range(self._reader.resolution_count(self._pyramid_image_index)))

    @property
    def base_metadata(self) -> Optional[WsiMetadata]:
        return None

    @staticmethod
    def _get_image_indices(
        reader: BioformatsReader,
    ) -> Tuple[int, Optional[int], Optional[int]]:
        image_indices = list(range(reader.images_count))
        overview_image_index = None
        label_image_index = None

        for image_index in image_indices.copy():
            image_name = reader.image_name(image_index)
            if image_name is None:
                continue
            if "macro" in image_name.lower() or "overview" in image_name.lower():
                overview_image_index = image_index
                image_indices.remove(image_index)
            elif "label" in image_name.lower():
                label_image_index = image_index
                image_indices.remove(image_index)

        pyramid_image_index = 0
        largest_image_width = None
        for image_index in image_indices:
            image_width = reader.size(image_index).width
            if largest_image_width is None or largest_image_width < image_width:
                pyramid_image_index = image_index
                largest_image_width = image_width
        return pyramid_image_index, label_image_index, overview_image_index

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        return BioformatsImageData(
            self._reader,
            self._tile_size,
            self._encoder,
            self._pyramid_image_index,
            level_index,
        )

    def _create_label_image_data(self) -> DicomizerImageData:
        assert self._label_image_index is not None
        return BioformatsImageData(
            self._reader, self._tile_size, self._encoder, self._label_image_index, 0
        )

    def _create_overview_image_data(self) -> DicomizerImageData:
        assert self._overview_image_index is not None
        return BioformatsImageData(
            self._reader, self._tile_size, self._encoder, self._overview_image_index, 0
        )

    def close(self) -> None:
        return self._reader.close()
