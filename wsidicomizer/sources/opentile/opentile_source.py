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
from typing import Any

from opentile import OpenTile
from opentile.tiff_format import TiffFormat
from pydicom import Dataset
from upath import UPath
from wsidicom.codec import Encoder
from wsidicom.codec.settings import Channels
from wsidicom.geometry import Size, SizeMm
from wsidicom.metadata import UidGenerator
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.config import get_settings
from wsidicomizer.dicomizer_source import DicomizerSource, PyramidLevel
from wsidicomizer.errors import SourceNotSupportedError
from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor, MetadataPreProcessor
from wsidicomizer.sources.opentile.opentile_image_data import (
    OpenTileAssociatedImageData,
    OpenTileLevelImageData,
    OpenTileOverlappingLevelImageData,
)
from wsidicomizer.sources.opentile.opentile_metadata import OpenTileMetadata
from wsidicomizer.wsi_format import WsiFormat


class OpenTileSource(DicomizerSource):
    def __init__(
        self,
        filepath: UPath,
        encoder: Encoder | None,
        tile_size: int | None = None,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        metadata_pre_processor: MetadataPreProcessor | None = None,
        force_transcoding: bool = False,
        uid_generator: UidGenerator | None = None,
        file_options: dict[str, Any] | None = None,
    ) -> None:
        """Create a new OpenTileSource.

        Parameters
        ----------
        filepath: UPath
            Path to the file, on any filesystem.
        encoder: Encoder | None
            Encoder to use. Pyramid is always re-encoded using the encoder.
            If None, the source picks a default matching its pixel format.
        tile_size: int | None = None
            Preferred tile size to use, if not enforced by file. Falls back to
            `get_settings().default_tile_size` if `None`. Only has effect for NDPI
            files where it controls how stripes are subdivided.
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        include_confidential: bool = True
            Include confidential metadata.
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None
            Optional metadata post processing by update from dataset or callback.
        metadata_pre_processor: MetadataPreProcessor | None = None
            Optional metadata pre processing by callback, of the metadata read
            from the file before `metadata` and `default_metadata` are merged
            into it.
        force_transcoding: bool = False
            If to force transcoding images.
        uid_generator: UidGenerator | None = None
            Generator used by the source to fill metadata UIDs. `None` uses the
            default `CallableUidGenerator` backed by `pydicom.generate_uid`.
        file_options: dict[str, Any] | None = None
            Options forwarded to the fsspec filesystem when reading a fsspec
            path. Ignored by sources that only read local files.
        """
        if tile_size is None:
            tile_size = get_settings().default_tile_size
        try:
            self._tiler = OpenTile.open(filepath, tile_size, file_options=file_options)
        except Exception as error:
            # OpenTile is tried first, and a file of a format it detects but can
            # not open (e.g. an OME-TIFF without a physical size) may still be
            # read by another source.
            raise SourceNotSupportedError(
                f"OpenTile can not open {filepath}: {error}"
            ) from error
        self._output_tile_size = tile_size
        try:
            format_name = self._tiler.format.name
            try:
                self._wsi_format = WsiFormat[format_name]
            except KeyError:
                self._wsi_format = WsiFormat.GENERIC
            self._base_metadata = OpenTileMetadata(
                self._tiler.metadata,
                self.has_label,
                self.has_overview,
                self._tiler.icc_profile,
                wsi_format=self._wsi_format,
                imaged_size=self._volume_imaged_size,
            )

            self._force_transcoding = force_transcoding
            super().__init__(
                filepath=filepath,
                encoder=encoder,
                tile_size=tile_size,
                metadata=metadata,
                default_metadata=default_metadata,
                include_confidential=include_confidential,
                metadata_post_processor=metadata_post_processor,
                metadata_pre_processor=metadata_pre_processor,
                uid_generator=uid_generator,
            )
        except BaseException:
            self._tiler.close()
            raise

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
    def prefer_regenerated_pyramid(self) -> bool:
        return self._reads_only_base_levels

    @property
    def pyramid_levels(self) -> list[PyramidLevel]:
        """The levels read: every level, or only the base levels for the formats
        whose pyramid is rebuilt from the base (Trestle, Ventana)."""
        pyramid_count = len(self._tiler.pyramids)
        if pyramid_count > 1:
            raise NotImplementedError(
                f"File holds {pyramid_count} pyramids (e.g. several ROIs); only one is "
                "supported."
            )
        base_pyramid_index = self._tiler.levels[0].pyramid_index
        return [
            PyramidLevel(
                0, level.pyramid_index, index, level.focal_plane, level.optical_path
            )
            for index, level in enumerate(self._tiler.levels)
            if not self._reads_only_base_levels
            or level.pyramid_index == base_pyramid_index
        ]

    @property
    def has_label(self) -> bool:
        return len(self._tiler.labels) > 0

    @property
    def has_overview(self) -> bool:
        return len(self._tiler.overviews) > 0

    @staticmethod
    def is_supported(
        path: str | Path | UPath, file_options: dict[str, Any] | None = None
    ) -> bool:
        """Return True if file in path is of a format OpenTile detects."""
        return OpenTile.detect_format(path, file_options) is not None

    @property
    def _reads_only_base_levels(self) -> bool:
        # Ventana stores overlapping tiles on every level, above the base at
        # fractional positions. Trestle's stored coarse levels are softer (scanner
        # downsampled, JPEG q75), slightly shrunk at level 2 and cropped from level
        # 3. Both pyramids are rebuilt from the base level instead.
        return self._tiler.format in (TiffFormat.TRESTLE, TiffFormat.VENTANA)

    def _create_level_image_data(self, level_index: int) -> BaseDicomizerImageData:
        level = self._tiler.levels[level_index]
        # A base level whose tiles overlap (Ventana, and Trestle when opentile
        # does not re-grid it): composed into non-overlapping output tiles.
        if level.overlap is not None:
            return OpenTileOverlappingLevelImageData(
                level,
                self.base_metadata.pyramid.image,
                self.metadata.pyramid.image,
                self._encoder,
                self._output_tile_size,
                self._decoded_frame_cache,
            )
        return OpenTileLevelImageData(
            level,
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
        """Return the imaged size of the volume. For overlapping levels the physical
        extent is the de-overlapped (composed) size, not the raw tile mosaic."""
        base_level = self._tiler.levels[0]
        if base_level.overlap is not None:
            size = base_level.overlap.image_size
        else:
            size = base_level.image_size
        return SizeMm(*base_level.pixel_spacing.to_tuple()) * Size(*size.to_tuple())
