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

"""Module containing a base ImageData implementation suitable for use with non-DICOM
files."""

from abc import ABCMeta, abstractmethod

import numpy as np
from wsidicom import ImageData
from wsidicom.geometry import Orientation, PointMm
from wsidicom.instance import ImageCoordinateSystem
from wsidicom.geometry import PointMm, Orientation

from wsidicomizer.encoding import Encoder


class DicomizerImageData(ImageData, metaclass=ABCMeta):
    """
    Metaclass for Dicomizer image data. Subclasses should implement all the abstract
    methods and properties in the base ImageData-class, and the pyramid_index property.
    """

    _default_z = None

    def __init__(self, encoder: Encoder):
        """Metaclass for Dicomized image data.

        Parameters
        ----------
        encoded: Encoder
            Encoder to use.
        """
        self._encoder = encoder

    @property
    @abstractmethod
    def pyramid_index(self) -> int:
        """Should return pyramid level for image data."""
        raise NotImplementedError()

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        """Return a default ImageCoordinateSystem."""
        return ImageCoordinateSystem(PointMm(0, 0), Orientation((0, 1, 0, 1, 0, 0)))

    def _encode(self, image_data: np.ndarray) -> bytes:
        """Return image data encoded in jpeg using set quality and subsample
        options.

        Parameters
        ----------
        image_data: np.ndarray
            Image data to encode.

        Returns
        ----------
        bytes
            Jpeg bytes.
        """
        return self._encoder.encode(image_data)
