#    Copyright 2025 SECTRA AB
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

"""Source for reading MIRAX (.mrxs) files with MiraxReader."""

from pathlib import Path
from typing import Any

import numpy as np
from pydicom import Dataset
from upath import UPath
from wsidicom.codec import Encoder
from wsidicom.codec.settings import Channels
from wsidicom.metadata import UidGenerator, WsiMetadata
from wsidicom.paths import as_local_path

from wsidicomizer.dicomizer_source import DicomizerSource, PyramidLevel
from wsidicomizer.errors import SourceNotSupportedError
from wsidicomizer.image_data import (
    BaseDicomizerImageData,
    PixelAssociatedImageData,
    PixelThumbnailImageData,
)
from wsidicomizer.metadata import (
    MetadataPostProcessor,
    MetadataPreProcessor,
    WsiDicomizerMetadata,
)
from wsidicomizer.sources.mirax.mirax_image_data import (
    MiraxFluorescenceLevelImageData,
    MiraxLevelImageData,
)
from wsidicomizer.sources.mirax.mirax_metadata import MiraxMetadata
from wsidicomizer.sources.mirax.reader import (
    MiraxAssociatedImageType,
    MiraxReader,
)


class MiraxSource(DicomizerSource):
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
        uid_generator: UidGenerator | None = None,
        file_options: dict[str, Any] | None = None,
        **source_args,
    ) -> None:
        """Create a new MiraxSource.

        Parameters
        ----------
        filepath: UPath
            Path to the .mrxs file. Must be on the local filesystem.
        encoder: Encoder | None
            Encoder to use. The pyramid is always re-encoded using the encoder. If
            None, the source picks a default matching its pixel format.
        tile_size: int | None
            Tile size to use. If None, the default tile size is used.
        metadata: WsiMetadata | None
            User-specified metadata that overloads metadata from the source file.
        default_metadata: WsiMetadata | None
            User-specified metadata used as default values.
        include_confidential: bool
            Include confidential metadata.
        metadata_post_processor: Dataset | MetadataPostProcessor | None
            Optional metadata post processing by update from dataset or callback.
        metadata_pre_processor: MetadataPreProcessor | None
            Optional metadata pre processing by callback, of the metadata read
            from the file before `metadata` and `default_metadata` are merged
            into it.
        uid_generator: UidGenerator | None
            Generator for the DICOM UIDs.
        file_options: dict[str, Any] | None
            Ignored; MIRAX slides are read from the local filesystem only.

        Raises
        ------
        SourceNotSupportedError
            If the slide is in a variant the reader refuses (reduced pyramid,
            >3-channel fluorescence, tiles without recorded positions, more than
            one position buffer), so that another source such as OpenSlide is
            tried.
        """
        try:
            self._mrxs = MiraxReader(str(self._require_local_filepath(filepath)))
        except NotImplementedError as error:
            raise SourceNotSupportedError(str(error)) from error
        try:
            self._base_metadata = MiraxMetadata(
                self._mrxs.slidedat, self._mrxs.bounds_offset
            )
            self._associated_images = self._mrxs.associated_images
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
            self._mrxs.close()
            raise

    @property
    def base_metadata(self) -> WsiDicomizerMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> list[PyramidLevel]:
        # only the base level is read (see prefer_regenerated_pyramid)
        return [PyramidLevel(0, 0, 0)]

    @property
    def prefer_regenerated_pyramid(self) -> bool:
        # Only the base level is read (the stored levels are mosaics of camera
        # photos at fractional positions), so the pyramid is built from it.
        return True

    @staticmethod
    def is_supported(
        path: str | Path | UPath, file_options: dict[str, Any] | None = None
    ) -> bool:
        """Return True if `path` is a local MIRAX slide (see
        MiraxReader.is_supported); variants the reader refuses are refused when
        the source is created.

        Parameters
        ----------
        path: str | Path | UPath
            Path to check. Paths not on the local filesystem are not supported.
        file_options: dict[str, Any] | None
            Ignored; MIRAX slides are read from the local filesystem only.

        Returns
        -------
        bool
            True if `path` is a local MIRAX slide.
        """
        local_path = as_local_path(path)
        if local_path is None:
            return False
        return MiraxReader.is_supported(local_path)

    def close(self) -> None:
        self._mrxs.close()

    @property
    def _pixel_format(self) -> tuple[Channels, int]:
        # fluorescence is served as grayscale channels, brightfield as RGB;
        # 16-bit fluorescence needs a 16-bit (uint16) encoder
        samples = 1 if self._mrxs.channels else 3
        dtype = np.uint16 if self._mrxs.slidedat.bit_depth == 16 else np.uint8
        return self._pixel_format_from(samples, np.dtype(dtype))

    def _create_level_image_data(self, level_index: int) -> BaseDicomizerImageData:
        """Return image data for the base level, the only level read.

        Parameters
        ----------
        level_index: int
            Level to wrap; always 0.

        Returns
        -------
        BaseDicomizerImageData
            Image data for the base level.
        """
        image_data_class = (
            MiraxFluorescenceLevelImageData
            if self._mrxs.channels
            else MiraxLevelImageData
        )
        return image_data_class(
            self._mrxs,
            self.metadata.pyramid.image,
            self._tile_size,
            self._encoder,
            self._decoded_frame_cache,
        )

    def _create_label_image_data(self) -> BaseDicomizerImageData | None:
        image = self._associated_images.get(MiraxAssociatedImageType.LABEL)
        if image is None:
            return None
        image_coordinate_system = None
        if self.metadata.label and self.metadata.label.image:
            image_coordinate_system = self.metadata.label.image.image_coordinate_system
        return PixelAssociatedImageData(
            image,
            self._mrxs.fill_color,
            self._encoder,
            image_coordinate_system=image_coordinate_system,
        )

    def _create_overview_image_data(self) -> BaseDicomizerImageData | None:
        image = self._associated_images.get(MiraxAssociatedImageType.MACRO)
        if image is None:
            return None
        image_coordinate_system = None
        if self.metadata.overview and self.metadata.overview.image:
            image_coordinate_system = (
                self.metadata.overview.image.image_coordinate_system
            )
        return PixelAssociatedImageData(
            image,
            self._mrxs.fill_color,
            self._encoder,
            image_coordinate_system=image_coordinate_system,
        )

    def _create_thumbnail_image_data(self) -> BaseDicomizerImageData | None:
        # The SlidePreview covers the whole nominal camera grid; crop it to the
        # tissue bounding box the pyramid covers, as openslide's bounds would.
        image = self._associated_images.get(MiraxAssociatedImageType.THUMBNAIL)
        if image is None:
            return None
        return PixelThumbnailImageData(
            image,
            self._mrxs.fill_color,
            self._mrxs.bounds_offset,
            self._mrxs.dimensions,
            self._mrxs.scan_dimensions,
            self.metadata.pyramid.image,
            self._encoder,
        )
