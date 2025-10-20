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

from functools import cached_property
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from opentile import OpenTile
from pydicom import Dataset
from wsidicom.codec import Encoder
from wsidicom.geometry import Size, SizeMm
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor
from wsidicomizer.sources.opentile.opentile_image_data import (
    OpenTileAssociatedImageData,
    OpenTileLevelImageData,
)
from wsidicomizer.sources.opentile.opentile_metadata import OpenTileMetadata


class OpenTileSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: int = 512,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_confidential: bool = True,
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None,
        force_transcoding: bool = False,
    ) -> None:
        """Create a new OpenTileSource.

        Parameters
        ----------
        filepath: Path
            Path to the file.
        encoder: Encoder
            Encoder to use. Pyramid is always re-encoded using the encoder.
        tile_size: int = 512,
            Preferred tile size to use, if not enforced by file.
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        include_confidential: bool = True
            Include confidential metadata.
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None
            Optional metadata post processing by update from dataset or callback.
        force_transcoding: bool = False
            If to force transcoding images.
        """
        self._tiler = OpenTile.open(filepath, tile_size)
        self._base_metadata = OpenTileMetadata(
            self._tiler.metadata, self._tiler.icc_profile
        )

        self._force_transcoding = force_transcoding
        super().__init__(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            metadata_post_processor,
        )

    def close(self):
        self._tiler.close()

    @property
    def base_metadata(self) -> OpenTileMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> Dict[Tuple[int, float, str], int]:
        return {
            (level.pyramid_index, level.focal_plane, level.optical_path): index
            for index, level in enumerate(self._tiler.levels)
            if (level.image_size.width >= self._tile_size and 
                level.image_size.height >= self._tile_size)
        }

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by OpenTile."""
        return OpenTile.detect_format(filepath) is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        return OpenTileLevelImageData(
            self._tiler.levels[level_index],
            self.base_metadata.image,
            self.metadata.image,
            self._encoder,
            self._volume_imaged_size,
            self._force_transcoding,
        )

    def _create_label_image_data(self) -> Optional[DicomizerImageData]:
        if len(self._tiler.labels) == 0:
            return None
            
        label = self._tiler.labels[0]
        # Check if label image is too small compared to tile size
        if (label.image_size.width < self._tile_size or 
            label.image_size.height < self._tile_size):
            # Skip label if it's smaller than tile size
            return None
            
        return OpenTileAssociatedImageData(
            label, self._encoder, self._force_transcoding
        )

    def _create_overview_image_data(self) -> Optional[DicomizerImageData]:
        if len(self._tiler.overviews) == 0:
            return None
            
        overview = self._tiler.overviews[0]
        # Check if overview image is too small compared to tile size
        if (overview.image_size.width < self._tile_size or 
            overview.image_size.height < self._tile_size):
            # Skip overview if it's smaller than tile size
            return None
            
        return OpenTileAssociatedImageData(
            overview, self._encoder, self._force_transcoding
        )

    def _create_thumbnail_image_data(self) -> Optional[DicomizerImageData]:

        if len(self._tiler.thumbnails) == 0:
            return None
            
        thumbnail = self._tiler.thumbnails[0]
        
        # Filter thumbnails smaller than tile size
        from wsidicomizer.config import settings
        actual_tile_size = self._tile_size or settings.default_tile_size
        width, height = thumbnail.size
        if width < actual_tile_size or height < actual_tile_size:
            return None
            
        return OpenTileLevelImageData(
            thumbnail,
            self.base_metadata.image,
            self.metadata.image,
            self._encoder,
            self._volume_imaged_size,
            self._force_transcoding,
        )

    @cached_property
    def _volume_imaged_size(self):
        """Return the imaged size of the volume."""
        base_level = self._tiler.levels[0]
        return SizeMm(*base_level.pixel_spacing.to_tuple()) * Size(
            *base_level.image_size.to_tuple()
        )
