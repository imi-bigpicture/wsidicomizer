import math
import os
from abc import ABCMeta
from ctypes import c_uint32
from typing import Literal

import numpy as np
import pydicom

from PIL import Image
from pydicom import config
from pydicom.uid import UID as Uid
from turbojpeg import TJPF_BGRA, TJSAMP_444, TurboJPEG
from wsidicom.geometry import Point, Size, SizeMm

from wsidicomizer.imagedata_wrapper import ImageDataWrapper

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

from openslide import OpenSlide
from openslide._convert import argb2rgba as convert_argb_to_rgba
from openslide.lowlevel import (ArgumentError, _read_associated_image,
                                _read_region, get_associated_image_dimensions,
                                get_associated_image_names)

"""
OpenSlideWrapper uses private functions from OpenSlide to get image data as
numpy arrays instead of pillow images. The private functions
(_read_associated_image, _read_region) are used to get raw data from the
OpenSlide C API. We consider this safe, as these directly map to the Openslide
C API and are thus not likely  to change.
"""

config.enforce_valid_values = True
config.future_behavior()


class OpenSlideWrapper(ImageDataWrapper, metaclass=ABCMeta):
    def __init__(
        self,
        open_slide: OpenSlide,
        jpeg: TurboJPEG,
        jpeg_quality: Literal = 95,
        jpeg_subsample: Literal = TJSAMP_444
    ):
        """Wraps a OpenSlide image to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        jpeg: TurboJPEG
            TurboJPEG object to use.
        jpeg_quality: Literal = 95
            Jpeg encoding quality to use.
        jpeg_subsample: Literal = TJSAMP_444
            Jpeg subsample option to use:
                TJSAMP_444 - no subsampling
                TJSAMP_420 - 2x2 subsampling
        """
        super().__init__(jpeg, jpeg_quality, jpeg_subsample, TJPF_BGRA)

        self._open_slide = open_slide

    @property
    def transfer_syntax(self) -> Uid:
        """The uid of the transfer syntax of the image."""
        return pydicom.uid.JPEGBaseline8Bit

    @property
    def pixel_format(self) -> Literal:
        return TJPF_BGRA

    @property
    def jpeg_quality(self) -> Literal:
        return self._jpeg_qualtiy

    @property
    def jpeg_subsample(self) -> Literal:
        raise self._jpeg_subsample

    @staticmethod
    def _make_transparent_pixels_white(image_data: np.ndarray) -> np.ndarray:
        """Removes transparency from image data. Openslide-python produces
        non-premultiplied, 'straigt' RGBA data and the RGB-part can be left
        unmodified. Fully transparent pixels have RGBA-value 0, 0, 0, 0. For
        these, we want full-white pixel instead of full-black.

        Parameters
        ----------
        image_data: np.ndarray
             Image data in RGBA pixel format to remove transparency from.

        Returns
        ----------
        image_data: np.ndarray
            Image data in RGBA pixel format without transparency.
        """
        transparency = image_data[:, :, 3]
        # Check for pixels with full transparency
        image_data[transparency == 0, :] = 255
        return image_data

    def close(self) -> None:
        """Close the open slide object, if not already closed."""
        try:
            self._open_slide.close()
        except ArgumentError:
            # Slide already closed
            pass


class OpenSlideAssociatedWrapper(OpenSlideWrapper):
    def __init__(
        self,
        open_slide: OpenSlide,
        image_type: str,
        jpeg: TurboJPEG,
        jpeg_quality: Literal = 95,
        jpeg_subsample: Literal = TJSAMP_444
    ):
        """Wraps a OpenSlide associated image (label or overview) to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        image_type: str
            Type of image to wrap.
        jpeg: TurboJPEG
            TurboJPEG object to use.
        jpeg_quality: Literal = 95
            Jpeg encoding quality to use.
        jpeg_subsample: Literal = TJSAMP_444
            Jpeg subsample option to use:
                TJSAMP_444 - no subsampling
                TJSAMP_420 - 2x2 subsampling
        """
        super().__init__(open_slide, jpeg, jpeg_quality, jpeg_subsample)
        self._image_type = image_type
        if image_type not in get_associated_image_names(self._open_slide._osr):
            raise ValueError(f"{image_type} not in {self._open_slide}")

        width, height = get_associated_image_dimensions(
            self._open_slide._osr,
            image_type
        )
        buffer = (width * height * c_uint32)()
        _read_associated_image(self._open_slide._osr, image_type, buffer)
        image_data: np.ndarray = np.frombuffer(buffer, dtype=np.uint8)
        image_data.shape = (width, height, 4)
        image_data = self._make_transparent_pixels_white(image_data)
        self._encoded_image = self._encode(image_data)
        convert_argb_to_rgba(image_data)
        self._decoded_image = Image.fromarray(image_data).convert('RGB')
        (height, width) = image_data.shape[0:2]
        self._image_size = Size(width, height)

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self.image_size

    @property
    def pixel_spacing(self) -> SizeMm:
        """Size of the pixels in mm/pixel."""
        # TODO figure out pixel spacing for label and overview in openslide.
        return SizeMm(1, 1)

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return 0

    def get_encoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
        if tile != Point(0, 0):
            raise ValueError
        return self._encoded_image

    def get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        if tile != Point(0, 0):
            raise ValueError
        return self._decoded_image


class OpenSlideLevelWrapper(OpenSlideWrapper):
    def __init__(
        self,
        open_slide: OpenSlide,
        level_index: Size,
        tile_size: int,
        jpeg: TurboJPEG,
        jpeg_quality: Literal = 95,
        jpeg_subsample: Literal = TJSAMP_444
    ):
        super().__init__(open_slide, jpeg, jpeg_quality, jpeg_subsample)
        """Wraps a OpenSlide level to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        level_index: int
            Level in OpenSlide object to wrap
        tile_size: Size
            Output tile size.
        jpeg: TurboJPEG
            TurboJPEG object to use.
        jpeg_quality: Literal = 95
            Jpeg encoding quality to use.
        jpeg_subsample: Literal = TJSAMP_444
            Jpeg subsample option to use:
                TJSAMP_444 - no subsampling
                TJSAMP_420 - 2x2 subsampling
        """
        self._tile_size = Size(tile_size, tile_size)
        self._open_slide = open_slide
        self._level_index = level_index
        self._jpeg = jpeg
        self._image_size = Size.from_tuple(
            self._open_slide.level_dimensions[self._level_index]
        )
        self._downsample = int(
            self._open_slide.level_downsamples[self._level_index]
        )
        self._pyramid_index = int(math.log2(self.downsample))

        base_mpp_x = float(self._open_slide.properties['openslide.mpp-x'])
        base_mpp_y = float(self._open_slide.properties['openslide.mpp-y'])
        self._pixel_spacing = SizeMm(
            base_mpp_x * self.downsample / 1000.0,
            base_mpp_y * self.downsample / 1000.0
        )

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @property
    def pixel_spacing(self) -> SizeMm:
        """Size of the pixels in mm/pixel."""
        return self._pixel_spacing

    @property
    def downsample(self) -> int:
        """Downsample facator for level."""
        return self._downsample

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return self._pyramid_index

    def _get_tile(self, tile: Point, flip: bool = False) -> np.ndarray:
        """Return tile as np array. Transparency is removed. Optionally the
        pixel format can be flipped to RGBA, suitable for opening with PIL.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        flip: bool
            If to flip the pixel format from ARGB to RGBA.

        Returns
        ----------
        np.ndarray
            Numpy array of tile.
        """
        tile_point_in_base_level = tile * self.downsample * self._tile_size
        if self._tile_size.width < 0 or self._tile_size.height < 0:
            raise ValueError('Negative size not allowed')
        buffer = (self._tile_size.width * self._tile_size.height * c_uint32)()
        _read_region(
            self._open_slide._osr,
            buffer,
            tile_point_in_base_level.x,
            tile_point_in_base_level.y,
            self._level_index,
            self._tile_size.width,
            self._tile_size.height
        )
        tile_data: np.ndarray = np.frombuffer(buffer, dtype=np.uint8)
        tile_data.shape = (self._tile_size.width, self._tile_size.height, 4)
        tile_data = self._make_transparent_pixels_white(tile_data)
        if flip:
            convert_argb_to_rgba(tile_data)
        return tile_data[:, :, 0:3]

    def get_encoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        """Return image bytes for tile. Transparency is removed and tile is
        encoded as jpeg.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        z: float
            Focal plane of tile to get.
        path: str
            Optical path of tile to get.

        Returns
        ----------
        bytes
            Tile bytes.
        """
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        return self._encode(self._get_tile(tile))

    def get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
        """Return Image for tile. Image mode is RGBA.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        z: float
            Focal plane of tile to get.
        path: str
            Optical path of tile to get.

        Returns
        ----------
        Image.Image
            Tile as Image.
        """
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        tile = self._get_tile(tile, True)
        return Image.fromarray(tile[:, :, 0:3])
