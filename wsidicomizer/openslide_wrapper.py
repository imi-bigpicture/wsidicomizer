import math
import os
from abc import ABCMeta
from ctypes import c_uint32
from pathlib import Path
from typing import List

import numpy as np

from PIL import Image
from pydicom import config
from pydicom.uid import UID as Uid
from wsidicom.geometry import Point, Size, SizeMm, Region
from wsidicom.errors import WsiDicomNotFoundError

from wsidicomizer.imagedata_wrapper import ImageDataWrapper
from wsidicomizer.encoding import Encoder


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
        encoder: Encoder
    ):
        """Wraps a OpenSlide image to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(encoder)

        self._open_slide = open_slide

    @property
    def files(self) -> List[Path]:
        return [Path(self._open_slide._filename)]

    @property
    def transfer_syntax(self) -> Uid:
        """The uid of the transfer syntax of the image."""
        return self._encoder.transfer_syntax

    @staticmethod
    def _make_transparent_pixels_white(image_data: np.ndarray) -> np.ndarray:
        """Return image data where all pixels with transparency is replaced
        by white pixels. Openslide returns fully transparent pixels with
        RGBA-value 0, 0, 0, 0 for 'sparse' areas. At the edge to 'sparse' areas
        there can also be partial transparency. This function 'aggresively'
        removes all transparent pixels (instead of calculating RGB-values
        with transparency for partial transparent pixels) as it is much,
        simpler, faster, and the partial transparency is at the edge of the
        ROIs.

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
        image_data[transparency != 255, :] = 255
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
        encoder: Encoder
    ):
        """Wraps a OpenSlide associated image (label or overview) to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        image_type: str
            Type of image to wrap.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(open_slide, encoder)
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

    def _get_encoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        if tile != Point(0, 0):
            raise ValueError
        return self._encoded_image

    def _get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
        if tile != Point(0, 0):
            raise ValueError
        return self._decoded_image


class OpenSlideLevelWrapper(OpenSlideWrapper):
    def __init__(
        self,
        open_slide: OpenSlide,
        level_index: int,
        tile_size: int,
        encoder: Encoder
    ):
        super().__init__(open_slide, encoder)
        """Wraps a OpenSlide level to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        level_index: int
            Level in OpenSlide object to wrap
        tile_size: int
            Output tile size.
        encoded: Encoder
            Encoder to use.
        """
        self._tile_size = Size(tile_size, tile_size)
        self._open_slide = open_slide
        self._level_index = level_index
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

    def stitch_tiles(
        self,
        region: Region,
        path: str,
        z: float
    ) -> Image.Image:
        """Overrides ImageData stitch_tiles() to read reagion directly from
        openslide object.

        Parameters
        ----------
        region: Region
             Pixel region to stitch to image
        path: str
            Optical path
        z: float
            Z coordinate

        Returns
        ----------
        Image.Image
            Stitched image
        """
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"Optical path {path}", str(self))
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"Z {z}", str(self))
        if region.size.width < 0 or region.size.height < 0:
            raise ValueError('Negative size not allowed')

        location_in_base_level = region.start * self.downsample

        buffer = (region.size.width * region.size.height * c_uint32)()
        _read_region(
            self._open_slide._osr,
            buffer,
            location_in_base_level.x,
            location_in_base_level.y,
            self._level_index,
            region.size.width,
            region.size.height
        )
        tile_data: np.ndarray = np.frombuffer(buffer, dtype=np.uint8)
        tile_data.shape = (region.size.width, region.size.height, 4)
        tile_data = self._make_transparent_pixels_white(tile_data)
        convert_argb_to_rgba(tile_data)
        return Image.fromarray(tile_data).convert('RGB')

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
        return tile_data

    def _get_encoded_tile(
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

    def _get_decoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str
    ) -> Image.Image:
        """Return Image for tile. Image mode is RGB.

        Parameters
        ----------
        tile_point: Point
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
        tile = self._get_tile(tile_point, True)
        return Image.fromarray(tile).convert('RGB')
