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

"""Source for reading MIRAX (.mrxs) files with MiraxReader.

Reuses OpenSlideLikeSource for the pyramid and associated-image plumbing, but
supplies its own MiraxMetadata."""

from pathlib import Path

import numpy as np
from pydicom import Dataset
from wsidicom.codec import Encoder
from wsidicom.codec.settings import Channels
from wsidicom.metadata import UidGenerator, WsiMetadata

from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor
from wsidicomizer.sources.mirax.mirax_image_data import (
    MiraxFluorescenceLevelImageData,
    MiraxLevelImageData,
)
from wsidicomizer.sources.mirax.mirax_metadata import MiraxMetadata
from wsidicomizer.sources.mirax.reader import MiraxReader
from wsidicomizer.sources.openslide_like import (
    OpenSlideLikeProperties,
    OpenSlideLikeSource,
)


class MiraxSource(OpenSlideLikeSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder | None,
        tile_size: int | None = None,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        uid_generator: UidGenerator | None = None,
        **source_args,
    ) -> None:
        """Create a new MiraxSource.

        Parameters
        ----------
        filepath: Path
            Path to the .mrxs file.
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
        uid_generator: UidGenerator | None
            Generator for the DICOM UIDs.
        """
        self._mrxs = MiraxReader(str(filepath))
        red, green, blue = self._mrxs.fill_color
        # OpenSlideLikeSource only needs the background color and (absent) bounds:
        # the reader origin is already the tissue bounding box, so there's no
        # offset. Everything else comes from MiraxMetadata.
        properties = OpenSlideLikeProperties(
            background_color=f"{red:02x}{green:02x}{blue:02x}",
        )
        super().__init__(
            filepath,
            properties,
            self._mrxs.level_downsamples,
            self._mrxs.level_dimensions,
            self._mrxs.associated_images,
            MiraxMetadata(self._mrxs.slidedat),
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            metadata_post_processor,
            uid_generator,
        )

    def close(self) -> None:
        self._mrxs.close()

    @property
    def _pixel_format(self) -> tuple[Channels, int]:
        # fluorescence is served as grayscale channels, brightfield as RGB;
        # 16-bit fluorescence needs a 16-bit (uint16) encoder
        samples = 1 if self._mrxs.channels else 3
        dtype = np.uint16 if self._mrxs.slidedat.bit_depth == 16 else np.uint8
        return self._pixel_format_from(samples, np.dtype(dtype))

    @staticmethod
    def is_supported(path: Path) -> bool:
        """Return True if `path` looks like a MIRAX slide.

        Detection is lightweight (see MiraxReader.is_supported); unsupported
        variants such as reduced/truncated pyramids pass here and are rejected when
        the reader is opened.

        Parameters
        ----------
        path: Path
            Path to check.

        Returns
        -------
        bool
            True if `path` is a .mrxs file with a Slidedat.ini alongside it.
        """
        return MiraxReader.is_supported(path)

    def _create_level_image_data(self, level_index: int) -> BaseDicomizerImageData:
        """Return image data for a pyramid level.

        Parameters
        ----------
        level_index: int
            Level in the reader to wrap.

        Returns
        -------
        BaseDicomizerImageData
            Image data for the level.
        """
        image_data_class = (
            MiraxFluorescenceLevelImageData
            if self._mrxs.channels
            else MiraxLevelImageData
        )
        return image_data_class(
            self._mrxs,
            self._blank_color,
            self.metadata.pyramid.image,
            level_index,
            self._tile_size,
            self._encoder,
        )
