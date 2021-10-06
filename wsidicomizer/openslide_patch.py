import os
from ctypes import c_uint32
from typing import Tuple

import numpy as np

if os.name == 'nt':  # On windows, add path to openslide to dll path
    try:
        openslide_dir = os.environ['OPENSLIDE']
    except KeyError:
        raise ValueError(
            "Enviroment variable 'OPENSLIDE'"
            "needs to be set to OpenSlide bin path"
        )
    try:
        os.add_dll_directory(openslide_dir)
    except AttributeError:
        os.environ['PATH'] = (
            openslide_dir + os.pathsep + os.environ['PATH']
        )

from openslide import OpenSlide, _AssociatedImageMap
from openslide.lowlevel import (_read_associated_image, _read_region,
                                get_associated_image_dimensions)


class _AssociatedImageMapNp(_AssociatedImageMap):
    def __getitem__(self, name: str) -> np.ndarray:
        """Return assoicated image identified by name as numpy array.

        Parameters
        ----------
        name: str
            Name of associated image to use (e.g. 'label')

        Returns
        ----------
        np.ndarray
            Associated image as numpy array with RGBA-pixel format.
        """
        if name not in self._keys():
            raise KeyError('Unkown associated image')
        width, height = get_associated_image_dimensions(self._osr, name)
        buffer = (width * height * c_uint32)()
        _read_associated_image(self._osr, name, buffer)
        data = np.frombuffer(buffer, dtype=np.uint8)
        data.shape = (width, height, 4)
        return data


class OpenSlidePatched(OpenSlide):
    @property
    def associated_images_np(self):
        """Return dictionary of associated image with numpy image data values.
        Each assoicated image is identified by a str name (e.g. 'label').

        Returns
        ----------
        _AssociatedImageMapNp
            Dictionary of assoicated images as numpy array.
        """
        return _AssociatedImageMapNp(self._osr)

    def read_region_np(
        self,
        location: Tuple[int, int],
        level: int,
        size: Tuple[int, int]
    ) -> np.ndarray:
        """Return region at location, level, and size as numpy array.


        Parameters
        ----------
        location: Tuple[int, int]
            Location to read from (in relation to base level).
        level: int
            Level to read from.
        size: Tuple[int, int]
            Size of region to read

        Returns
        ----------
        np.ndarray
            Image data as numpy array with RGBA-pixel format.
        """
        (width, height) = size
        if width < 0 or height < 0:
            raise ValueError('Negative size not allowed')
        (x, y) = location
        buffer = (width * height * c_uint32)()
        _read_region(self._osr, buffer, x, y, level, width, height)
        data = np.frombuffer(buffer, dtype=np.uint8)
        data.shape = (width, height, 4)
        return data
