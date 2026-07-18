#    Copyright 2023, 2025 SECTRA AB

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

"""Source for reading tiffslide compatible file."""

from pathlib import Path
from typing import Any

from pydicom import Dataset
from tiffslide import TiffSlide
from tiffslide.tiffslide import (
    PROPERTY_NAME_BACKGROUND_COLOR,
    PROPERTY_NAME_BOUNDS_HEIGHT,
    PROPERTY_NAME_BOUNDS_WIDTH,
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    PROPERTY_NAME_MPP_X,
    PROPERTY_NAME_MPP_Y,
    PROPERTY_NAME_OBJECTIVE_POWER,
    PROPERTY_NAME_VENDOR,
)
from upath import UPath
from wsidicom.codec import Encoder
from wsidicom.codec.settings import Channels
from wsidicom.metadata import UidGenerator, WsiMetadata

from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor
from wsidicomizer.sources.openslide_like import (
    OpenSlideLikeProperties,
    OpenSlideLikeSource,
)
from wsidicomizer.sources.openslide_like.openslide_like_metadata import (
    OpenSlideLikeMetadata,
)
from wsidicomizer.sources.tiffslide.tiffslide_image_data import (
    TiffSlideLevelImageData,
)


class TiffSlideSource(OpenSlideLikeSource):
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
        file_options: dict[str, Any] | None = None,
        **source_args,
    ) -> None:
        """Create a new TiffSlideSource.

        Parameters
        ----------
        filepath: Path
            Path to the file.
        encoder: Encoder | None
            Encoder to use. Pyramid is always re-encoded using the encoder.
            If None, the source picks a default matching its pixel format.
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
        uid_generator: UidGenerator | None = None
            Generator used by the source to fill metadata UIDs. `None` uses the
            default `CallableUidGenerator` backed by `pydicom.generate_uid`.
        file_options: dict[str, Any] | None = None
            Options forwarded to the fsspec filesystem when reading a fsspec
            path. Ignored by sources that only read local files.
        """
        self._tiffslide = TiffSlide(
            filepath, storage_options=file_options, **source_args
        )
        properties = OpenSlideLikeProperties(
            background_color=self._tiffslide.properties.get(
                PROPERTY_NAME_BACKGROUND_COLOR
            ),
            bounds_x=self._tiffslide.properties.get(PROPERTY_NAME_BOUNDS_X),
            bounds_y=self._tiffslide.properties.get(PROPERTY_NAME_BOUNDS_Y),
            bounds_height=self._tiffslide.properties.get(PROPERTY_NAME_BOUNDS_HEIGHT),
            bounds_width=self._tiffslide.properties.get(PROPERTY_NAME_BOUNDS_WIDTH),
            objective_power=self._tiffslide.properties.get(
                PROPERTY_NAME_OBJECTIVE_POWER
            ),
            vendor=self._tiffslide.properties.get(PROPERTY_NAME_VENDOR),
            mpp_x=self._tiffslide.properties.get(PROPERTY_NAME_MPP_X),
            mpp_y=self._tiffslide.properties.get(PROPERTY_NAME_MPP_Y),
            raw_properties=dict(self._tiffslide.properties),
        )

        super().__init__(
            filepath,
            properties,
            self._tiffslide.level_downsamples,
            self._tiffslide.level_dimensions,
            self._tiffslide.associated_images,
            OpenSlideLikeMetadata(properties, self._tiffslide.color_profile),
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            metadata_post_processor,
            uid_generator,
            file_options,
        )

    def close(self):
        self._tiffslide.close()

    @property
    def _pixel_format(self) -> tuple[Channels, int]:
        axes = self._tiffslide.properties.get("tiffslide.series-axes")
        samples_per_pixel = 1 if axes == "YX" else 3
        dtype = self._tiffslide.ts_tifffile.series[0].dtype
        return self._pixel_format_from(samples_per_pixel, dtype)

    @staticmethod
    def is_supported(
        path: Path | UPath, file_options: dict[str, Any] | None = None
    ) -> bool:
        """Return True if file in path is supported by TiffSlide. A path whose
        fsspec backend is unavailable or unreadable is treated as unsupported so
        source selection stays robust (mirrors opentile's defensive detection)."""
        try:
            format = TiffSlide.detect_format(path, storage_options=file_options)
        except Exception:
            return False
        return format is not None

    def _create_level_image_data(self, level_index: int) -> BaseDicomizerImageData:
        return TiffSlideLevelImageData(
            self._tiffslide,
            self._blank_color,
            self._base_level_offset,
            self._base_level_size,
            self.metadata.pyramid.image,
            level_index,
            self._tile_size,
            self._encoder,
        )
