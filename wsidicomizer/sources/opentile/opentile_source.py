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

from opentile import OpenTile
from pydicom import Dataset
from wsidicom.codec import Encoder
from wsidicom.codec.settings import Channels
from wsidicom.geometry import Size, SizeMm
from wsidicom.metadata import UidGenerator
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.config import get_settings
from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor
from wsidicomizer.sources.opentile.opentile_image_data import (
    OpenTileAssociatedImageData,
    OpenTileLevelImageData,
)
from wsidicomizer.sources.opentile.opentile_metadata import OpenTileMetadata
from wsidicomizer.wsi_format import WsiFormat


class OpenTileSource(DicomizerSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder | None,
        tile_size: int | None = None,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        force_transcoding: bool = False,
        uid_generator: UidGenerator | None = None,
    ) -> None:
        """Create a new OpenTileSource.

        Parameters
        ----------
        filepath: Path
            Path to the file.
        encoder: Encoder | None
            Encoder to use. Pyramid is always re-encoded using the encoder.
            If None, the source picks a default matching its pixel format.
        tile_size: int | None = None
            Preferred tile size to use, if not enforced by file. Falls back to
            `settings.default_tile_size` if `None`. Only has effect for NDPI
            files where it controls how stripes are subdivided.
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
        if tile_size is None:
            tile_size = settings.default_tile_size
        self._tiler = OpenTile.open(filepath, tile_size)
        # opentile's TiffFormat member names match WsiFormat member names.
        self._wsi_format = WsiFormat[self._tiler.format.name]
        self._base_metadata = OpenTileMetadata(
            self._tiler.metadata,
            self.has_label,
            self.has_overview,
            self._tiler.icc_profile,
            wsi_format=self._wsi_format,
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
            uid_generator,
        )

    def close(self):
        self._tiler.close()

    @property
    def _pixel_format(self) -> tuple[Channels, int]:
        base = self._tiler.levels[0]
        return self._pixel_format_from(base.samples_per_pixel, base.np_dtype)

    @property
    def base_metadata(self) -> OpenTileMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> dict[tuple[int, float, str], int]:
        return {
            (level.pyramid_index, level.focal_plane, level.optical_path): index
            for index, level in enumerate(self._tiler.levels)
        }

    @property
    def has_label(self) -> bool:
        return len(self._tiler.labels) > 0

    @property
    def has_overview(self) -> bool:
        return len(self._tiler.overviews) > 0

    @staticmethod
    def is_supported(path: Path) -> bool:
        """Return True if file in path is supported by OpenTile. Formats whose tiles
        overlap (e.g. Trestle, Ventana) are not composed by this source yet and are
        left for another source to handle."""
        if OpenTile.detect_format(path) is None:
            return False
        with OpenTile.open(path) as tiler:
            return tiler.get_level(0).overlap is None

    def _create_level_image_data(self, level_index: int) -> BaseDicomizerImageData:
        return OpenTileLevelImageData(
            self._tiler.levels[level_index],
            self.base_metadata.pyramid.image,
            self.metadata.pyramid.image,
            self._encoder,
            self._volume_imaged_size,
            self._force_transcoding,
        )

    def _create_label_image_data(self) -> BaseDicomizerImageData | None:
        if not self.has_label:
            return None
        label_image_coordinate_system = None
        if self.metadata.label and self.metadata.label.image:
            label_image_coordinate_system = (
                self.metadata.label.image.image_coordinate_system
            )
        return OpenTileAssociatedImageData(
            self._tiler.labels[0],
            self._encoder,
            self._force_transcoding,
            image_coordinate_system=label_image_coordinate_system,
        )

    def _create_overview_image_data(self) -> BaseDicomizerImageData | None:
        if not self.has_overview:
            return None
        overview_image_coordinate_system = None
        if self.metadata.overview and self.metadata.overview.image:
            overview_image_coordinate_system = (
                self.metadata.overview.image.image_coordinate_system
            )
        return OpenTileAssociatedImageData(
            self._tiler.overviews[0],
            self._encoder,
            self._force_transcoding,
            image_coordinate_system=overview_image_coordinate_system,
        )

    def _create_thumbnail_image_data(self) -> BaseDicomizerImageData | None:

        if len(self._tiler.thumbnails) == 0:
            return None
        return OpenTileLevelImageData(
            self._tiler.thumbnails[0],
            self.base_metadata.pyramid.image,
            self.metadata.pyramid.image,
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
