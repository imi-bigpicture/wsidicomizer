#    Copyright 2021, 2022, 2023, 2025 SECTRA AB
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

"""Source for reading openslide compatible file."""

from pathlib import Path
from typing import Optional, Union

from pydicom import Dataset
from wsidicom.codec import Encoder
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.extras.openslide.openslide import (
    PROPERTY_NAME_BACKGROUND_COLOR,
    PROPERTY_NAME_BOUNDS_HEIGHT,
    PROPERTY_NAME_BOUNDS_WIDTH,
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    PROPERTY_NAME_MPP_X,
    PROPERTY_NAME_MPP_Y,
    PROPERTY_NAME_OBJECTIVE_POWER,
    PROPERTY_NAME_VENDOR,
    OpenSlide,
)
from wsidicomizer.extras.openslide.openslide_image_data import (
    OpenSlideLevelImageData,
)
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor
from wsidicomizer.sources.openslide_like import (
    OpenSlideLikeProperties,
    OpenSlideLikeSource,
)
from wsidicomizer.sources.openslide_like.openslide_like_metadata import (
    OpenSlideLikeMetadata,
)


class OpenSlideSource(OpenSlideLikeSource):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: Optional[int] = None,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        include_confidential: bool = True,
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None,
    ) -> None:
        """Create a new OpenSlideSource.

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
        """
        self._slide = OpenSlide(filepath)
        properties = OpenSlideLikeProperties(
            background_color=self._slide.properties.get(PROPERTY_NAME_BACKGROUND_COLOR),
            bounds_x=self._slide.properties.get(PROPERTY_NAME_BOUNDS_X),
            bounds_y=self._slide.properties.get(PROPERTY_NAME_BOUNDS_Y),
            bounds_width=self._slide.properties.get(PROPERTY_NAME_BOUNDS_WIDTH),
            bounds_height=self._slide.properties.get(PROPERTY_NAME_BOUNDS_HEIGHT),
            objective_power=self._slide.properties.get(PROPERTY_NAME_OBJECTIVE_POWER),
            vendor=self._slide.properties.get(PROPERTY_NAME_VENDOR),
            mpp_x=self._slide.properties.get(PROPERTY_NAME_MPP_X),
            mpp_y=self._slide.properties.get(PROPERTY_NAME_MPP_Y),
        )
        super().__init__(
            filepath,
            properties,
            self._slide.level_downsamples,
            self._slide.level_dimensions,
            self._slide.associated_images,
            OpenSlideLikeMetadata(properties, self._slide.color_profile),
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            metadata_post_processor,
        )

    def close(self) -> None:
        return self._slide.close()

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by OpenSlide."""
        return OpenSlide.detect_format(str(filepath)) is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        return OpenSlideLevelImageData(
            self._slide,
            self._blank_color,
            self._base_level_offset,
            self._base_level_size,
            self.metadata.pyramid.image,
            level_index,
            self._tile_size,
            self._encoder,
        )
