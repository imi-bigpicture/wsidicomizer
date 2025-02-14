#    Copyright 2024 SECTRA AB
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

"""Source for reading libisyntax compatible file."""

from pathlib import Path
from typing import Dict, Optional, Union

from pydicom import Dataset
from wsidicom.codec import Encoder
from wsidicom.metadata import WsiMetadata

from isyntax import ISyntax
from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.extras.isyntax.isyntax_image_data import (
    ISyntaxAssociatedImageImageData,
    ISyntaxLevelImageData,
)
from wsidicomizer.extras.isyntax.isyntax_metadata import ISyntaxMetadata
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor, WsiDicomizerMetadata


class ISyntaxSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: Optional[int] = None,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_confidential: bool = True,
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None,
        force_transcoding: bool = False,
        cache: int = 2048,
    ) -> None:
        """Create a new ISyntaxSource.

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
        force_transcoding: bool = False
            If to force transcoding of label and overview images.
        cache: int = 2048
            Cache size to use for ISyntax.
        """
        self._slide = ISyntax.open(filepath, cache)
        self._force_transcoding = force_transcoding
        self._base_metadata = ISyntaxMetadata(self._slide)
        super().__init__(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            metadata_post_processor,
        )

    @staticmethod
    def is_supported(path: Path) -> bool:
        try:
            ISyntax.open(path)
        except Exception:
            return False
        return True

    @property
    def base_metadata(self) -> WsiDicomizerMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> Dict[int, int]:
        return {0: 0}

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        return ISyntaxLevelImageData(
            self._slide,
            self.metadata.image,
            self._tile_size,
            self._encoder,
            level_index,
        )

    def _create_label_image_data(self) -> Optional[DicomizerImageData]:
        label = self._slide.read_label_image_jpeg()
        if label is None:
            return None
        return ISyntaxAssociatedImageImageData(
            label.tobytes(), self._encoder, self._force_transcoding
        )

    def _create_overview_image_data(self) -> Optional[DicomizerImageData]:
        overview = self._slide.read_macro_image_jpeg()
        if overview is None:
            return None
        return ISyntaxAssociatedImageImageData(
            overview.tobytes(), self._encoder, self._force_transcoding
        )

    def _create_thumbnail_image_data(self) -> Optional[DicomizerImageData]:
        return None

    def close(self) -> None:
        return self._slide.close()
