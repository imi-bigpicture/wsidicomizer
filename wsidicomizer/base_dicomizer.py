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

from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import List, Optional, Sequence, Union
from PIL.Image import Image as PILImage
from opentile.metadata import Metadata
from pydicom import Dataset, config
from pydicom.dataset import Dataset
from wsidicom import (WsiDicomLabels, WsiDicomLevels,
                      WsiDicomOverviews, WsiInstance)
from wsidicom.dataset import ImageType

from wsidicomizer.dataset import create_base_dataset, populate_base_dataset
from wsidicomizer.encoding import Encoder
from wsidicomizer.image_data import DicomizerImageData

config.enforce_valid_values = True
config.future_behavior()


class BaseDicomizer(metaclass=ABCMeta):
    """Metaclass for Dicomizers. Subclasses should implement is_supported() and
    open().
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
            self.metadata,
            create_base_dataset(modules),
            include_confidential
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
    def _create_label_image_data(self,) -> DicomizerImageData:
        """Return image data instance for label."""
        raise NotImplementedError()

    @abstractmethod
    def _create_overview_image_data(self) -> DicomizerImageData:
        """Return image data instance for overview."""
        raise NotImplementedError()

    def create_levels(
        self,
        include_levels: Optional[Sequence[int]] = None,
    ) -> WsiDicomLevels:
        """Return levels from file

        Parameters
        ----------
        include_levels: Optional[Sequence[int]] = None
            Optional list indices (in present levels) to include, e.g. [0, 1]
            includes the two lowest levels. Negative indicies can be used,
            e.g. [-1, -2] includes the two highest levels.

        Returns
        ----------
        WsiDicomLevels
            Created levels.
        """
        level_instances = [
            WsiInstance.create_instance(
                self._create_level_image_data(level_index),
                self._base_dataset,
                ImageType.VOLUME
            )
            for level_index in range(len(self.pyramid_levels))
            if self._is_included_level(
                self.pyramid_levels[level_index],
                self.pyramid_levels,
                include_levels
            )
        ]
        return WsiDicomLevels.open(level_instances)

    def create_labels(
        self,
        include_label: bool,
        label: Optional[Union[PILImage, str, Path]] = None
    ) -> Optional[WsiDicomLabels]:
        """Return labels from file

        Parameters
        ----------
        include_label: bool
            Include label(s).
        label: Optional[Union[PILImage, str, Path]] = None
            Optional label image to use instead of label found in file.

        Returns
        ----------
        Optional[WsiDicomLabels]
            Created labels.
        """
        if include_label:
            if label is not None:
                label_instance = WsiInstance.create_label(
                    label,
                    self._base_dataset,
                )
            elif self.has_label:
                label_instance = WsiInstance.create_instance(
                    self._create_label_image_data(),
                    self._base_dataset,
                    ImageType.LABEL
                )
            else:
                return None
            return WsiDicomLabels.open([label_instance])
        return None

    def create_oveviews(
        self,
        include_overview: bool
    ) -> Optional[WsiDicomOverviews]:
        """Return overviews from file

        Parameters
        ----------
        include_overwiew: bool
            Include overview(s).

        Returns
        ----------
        Optional[WsiDicomOverviews]
            Created overviews.
        """
        if include_overview and self.has_overview:
            overview_instance = WsiInstance.create_instance(
                self._create_overview_image_data(),
                self._base_dataset,
                ImageType.OVERVIEW
            )
            return WsiDicomOverviews.open([overview_instance])
        return None

    @staticmethod
    def _is_included_level(
        level: int,
        present_levels: Sequence[int],
        include_indices: Optional[Sequence[int]] = None
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
            present_levels[level] for level in include_indices
            if -len(present_levels) <= level < len(present_levels)
        ]
        return level in absolute_levels
