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
from pathlib import Path
from typing import List, Optional, Sequence, Union

from opentile.metadata import Metadata
from pydicom import Dataset, config
from wsidicom.codec import Encoder
from wsidicom.graphical_annotations import AnnotationInstance
from wsidicom.instance import ImageType, WsiDataset, WsiInstance
from wsidicom.source import Source

from wsidicomizer.dataset import create_base_dataset, populate_base_dataset
from wsidicomizer.image_data import DicomizerImageData

config.enforce_valid_values = True
config.future_behavior()


class DicomizerSource(Source, metaclass=ABCMeta):
    """
    Metaclass for Dicomizer sources. Subclasses should implement the method
    is_supported(), _create_level_image_data(), _create_label_image_data(), and
     _create_overview_image_data() and the properties metadata, pyramid_levels,
     has_label, and has_overview. Subclasses can override the __init__().
    """

    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: int = 512,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        include_confidential: bool = True,
    ) -> None:
        self._filepath = filepath
        self._encoder = encoder
        self._tile_size = tile_size
        self._modules = modules
        self._include_confidential = include_confidential
        self._base_dataset = populate_base_dataset(
            self.metadata, create_base_dataset(modules), include_confidential
        )

    @staticmethod
    @abstractmethod
    def is_supported(path: Path) -> bool:
        """Return True if file in filepath is supported by Dicomizer."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def metadata(self) -> Metadata:
        """Return metadata for file."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def pyramid_levels(self) -> List[int]:
        """Return pyramid levels (scalings) for file."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def has_label(self) -> bool:
        """Return True if file has a label image."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def has_overview(self) -> bool:
        """Return True if file has a overview image."""
        raise NotImplementedError()

    @abstractmethod
    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        """Return image data instance for level."""
        raise NotImplementedError()

    @abstractmethod
    def _create_label_image_data(
        self,
    ) -> DicomizerImageData:
        """Return image data instance for label."""
        raise NotImplementedError()

    @abstractmethod
    def _create_overview_image_data(self) -> DicomizerImageData:
        """Return image data instance for overview."""
        raise NotImplementedError()

    @property
    def base_dataset(self) -> WsiDataset:
        return WsiDataset(self._base_dataset)

    @property
    def level_instances(self) -> List[WsiInstance]:
        return [
            WsiInstance.create_instance(
                self._create_level_image_data(level_index),
                self._base_dataset,
                ImageType.VOLUME,
            )
            for level_index in range(len(self.pyramid_levels))
        ]

    @property
    def label_instances(self) -> List[WsiInstance]:
        if not self.has_label:
            return []

        label = WsiInstance.create_instance(
            self._create_label_image_data(), self._base_dataset, ImageType.LABEL
        )
        return [label]

    @property
    def overview_instances(self) -> List[WsiInstance]:
        if not self.has_overview:
            return []

        overview = WsiInstance.create_instance(
            self._create_overview_image_data(), self._base_dataset, ImageType.OVERVIEW
        )
        return [overview]

    @property
    def annotation_instances(self) -> List[AnnotationInstance]:
        return []

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
            includes the two lowest levels. Negative indicies can be used,
            e.g. [-1, -2] includes the two highest levels. Default of None
            will not limit the selection. An empty sequence will exluded all
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
