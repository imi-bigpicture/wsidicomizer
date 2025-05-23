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

"""Module containing a base Source implementation suitable for use with non-DICOM
files."""

from abc import ABCMeta, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from pydicom import Dataset, config
from wsidicom import ImageData
from wsidicom.codec import Encoder
from wsidicom.graphical_annotations import AnnotationInstance
from wsidicom.instance import ImageType, WsiDataset, WsiInstance
from wsidicom.metadata import WsiMetadata
from wsidicom.metadata.schema.dicom import WsiMetadataDicomSchema
from wsidicom.source import Source

from wsidicomizer.config import settings
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor, WsiDicomizerMetadata

config.enforce_valid_values = True
config.future_behavior()


class DicomizerSource(Source, metaclass=ABCMeta):
    """
    Metaclass for Dicomizer sources. Subclasses should implement the method
    is_supported(), _create_level_image_data(), _create_label_image_data(), and
     _create_overview_image_data() and the properties metadata, pyramid_levels.
     Subclasses can override the __init__().
    """

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
        """Create a new DicomizerSource.

        Parameters
        ----------
        filepath: Path
            Path to the file.
        encoder: Encoder
            Encoder to use. Pyramid is always re-encoded using the encoder.
        tile_size: Optional[int]
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
        self._filepath = filepath
        self._encoder = encoder
        self._tile_size = tile_size
        self._user_metadata = metadata
        self._default_metadata = default_metadata
        self._include_confidential = include_confidential
        self._metadata_post_processor = metadata_post_processor

    @staticmethod
    @abstractmethod
    def is_supported(path: Path) -> bool:
        """Return True if file in filepath is supported by Dicomizer."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def base_metadata(self) -> WsiDicomizerMetadata:
        """Return metadata for file."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def pyramid_levels(self) -> Dict[Tuple[int, float, str], int]:
        """Dictionary of pyramid level (scalings), focal plane, and optical path as key
        and level index in file as value for levels in file."""
        raise NotImplementedError()

    @abstractmethod
    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        """Return image data instance for level."""
        raise NotImplementedError()

    @abstractmethod
    def _create_label_image_data(self) -> Optional[DicomizerImageData]:
        """Return image data instance for label."""
        raise NotImplementedError()

    @abstractmethod
    def _create_overview_image_data(self) -> Optional[DicomizerImageData]:
        """Return image data instance for overview."""
        raise NotImplementedError()

    @abstractmethod
    def _create_thumbnail_image_data(self) -> Optional[DicomizerImageData]:
        """Return image data instance for thumbnail."""
        raise NotImplementedError()

    @cached_property
    def metadata(self) -> WsiDicomizerMetadata:
        return self.base_metadata.merge(
            self.user_metadata, self.default_metadata, self._include_confidential
        )

    @property
    def user_metadata(self) -> Optional[WsiMetadata]:
        return self._user_metadata

    @property
    def default_metadata(self) -> Optional[WsiMetadata]:
        return self._default_metadata

    @property
    def base_dataset(self) -> WsiDataset:
        return self.level_instances[0].dataset

    @cached_property
    def level_instances(self) -> List[WsiInstance]:
        return [
            self._create_instance(
                self._create_level_image_data(level_index),
                ImageType.VOLUME,
                pyramid_index,
            )
            for (
                pyramid_index,
                _,
                _,
            ), level_index in self.pyramid_levels.items()
        ]

    @cached_property
    def label_instances(self) -> List[WsiInstance]:
        label = self._create_label_image_data()
        if label is None:
            return []
        return [self._create_instance(label, ImageType.LABEL)]

    @cached_property
    def overview_instances(self) -> List[WsiInstance]:
        overview = self._create_overview_image_data()
        if overview is None:
            return []
        return [self._create_instance(overview, ImageType.OVERVIEW)]

    @cached_property
    def thumbnail_instances(self) -> List[WsiInstance]:
        thumbnail = self._create_thumbnail_image_data()
        if thumbnail is None:
            return []
        return [self._create_instance(thumbnail, ImageType.THUMBNAIL)]

    @property
    def annotation_instances(self) -> List[AnnotationInstance]:
        return []

    def _create_instance(
        self,
        image_data: ImageData,
        image_type: ImageType,
        pyramid_index: Optional[int] = None,
    ) -> WsiInstance:
        """Create instance from image data."""
        dataset = self._create_dataset(
            image_type, image_data.photometric_interpretation
        )
        return WsiInstance.create_instance(
            image_data, dataset, image_type, pyramid_index
        )

    def _create_dataset(
        self, image_type: ImageType, photometric_interpretation: str
    ) -> WsiDataset:
        if (
            settings.insert_icc_profile_if_missing
            and not photometric_interpretation.startswith("MONOCHROME")
        ):
            metadata = self.metadata.insert_default_icc_profile()
        else:
            metadata = self.metadata
        dataset = WsiMetadataDicomSchema(context={"image_type": image_type}).dump(
            metadata
        )
        if isinstance(self._metadata_post_processor, Dataset):
            dataset.update(self._metadata_post_processor)
        elif callable(self._metadata_post_processor):
            dataset = self._metadata_post_processor(dataset, metadata)
        return WsiDataset(dataset)

    @staticmethod
    def _is_included_level(
        level: int,
        present_levels: Sequence[int],
        include_indices: Optional[Sequence[int]] = None,
    ) -> bool:
        """Return true if pyramid level is in included levels.

        Parameters
        ----------
        level: int
            Pyramid level to check.
        present_levels: Sequence[int]
            List of pyramid levels present.
        include_indices: Optional[Sequence[int]] = None
            Optional list indices (in present levels) to include, e.g. [0, 1]
            includes the two lowest levels. Negative indices can be used,
            e.g. [-1, -2] includes the two highest levels. Default of None
            will not limit the selection. An empty sequence will excluded all
            levels.

        Returns
        ----------
        bool
            True if level should be included.
        """
        if level not in present_levels:
            return False
        if include_indices is None:
            return True
        absolute_levels = [
            present_levels[level]
            for level in include_indices
            if -len(present_levels) <= level < len(present_levels)
        ]
        return level in absolute_levels
