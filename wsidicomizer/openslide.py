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

import ctypes
from enum import Enum
import math
import os
import re
from ctypes.util import find_library
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
from opentile.metadata import Metadata
from PIL import Image
from PIL.Image import Image as PILImage
from pydicom import Dataset
from pydicom.uid import UID as Uid
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, Region, Size, SizeMm

from wsidicomizer.base_dicomizer import BaseDicomizer
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.encoding import Encoder

# On windows, use find_library to find directory with openslide dll in
# the Path environmental variable.
if os.name == 'nt':
    openslide_lib_path = find_library('libopenslide-0')
    if openslide_lib_path is not None:
        openslide_dir = str(Path(openslide_lib_path).parent)
    else:
        openslide_lib_dir = os.environ.get('OPENSLIDE')
        if openslide_lib_dir is not None:
            openslide_lib_path = Path(openslide_lib_dir).joinpath(
                'libopenslide-0.dll'
            )
            if not openslide_lib_path.exists():
                openslide_lib_path = None
    if openslide_lib_path is None:
        raise ModuleNotFoundError(
            "Could not find libopenslide-0.dll in the directories specified "
            "in the `Path` or `OPENSLIDE` environmental variable. Please add "
            "the directory with openslide bin content to the `Path` or  "
            "OPENSLIDE environmental variable."
        )
    openslide_dir = str(Path(openslide_lib_path).parent)
    os.add_dll_directory(openslide_dir)

"""
OpenSlideImageData uses proteted functions from OpenSlide-Python to get image
data as numpy arrays instead of pillow images. The proteted function
_read_region is used to get raw data from the OpenSlide C API and argb2rgba is
used to convert argb to rgba. We consider this safe, as these directly map
to the Openslide C API and are thus not likely to change that often.
"""

from openslide import (PROPERTY_NAME_BACKGROUND_COLOR,
                       PROPERTY_NAME_BOUNDS_HEIGHT, PROPERTY_NAME_BOUNDS_WIDTH,
                       PROPERTY_NAME_BOUNDS_X, PROPERTY_NAME_BOUNDS_Y,
                       PROPERTY_NAME_MPP_X, PROPERTY_NAME_MPP_Y,
                       PROPERTY_NAME_OBJECTIVE_POWER, PROPERTY_NAME_VENDOR,
                       OpenSlide)
from openslide._convert import argb2rgba as convert_argb_to_rgba
from openslide.lowlevel import _read_region, get_associated_image_names


class OpenSlideAssociatedImageType(Enum):
    LABEL = 'label'
    MACRO = 'macro'


class OpenSlideMetadata(Metadata):
    def __init__(self, slide: OpenSlide):
        magnification = slide.properties.get(
            PROPERTY_NAME_OBJECTIVE_POWER
        )
        if magnification is not None:
            self._magnification = float(magnification)
        else:
            self._magnification = None
        self._scanner_manufacturer = slide.properties.get(
            PROPERTY_NAME_VENDOR
        )

    @property
    def magnification(self) -> Optional[float]:
        return self._magnification

    @property
    def scanner_manufacturer(self) -> Optional[str]:
        return self._scanner_manufacturer


class OpenSlideImageData(DicomizerImageData):
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
        self._slide = open_slide
        self._blank_color = self._get_blank_color(
            self.photometric_interpretation
        )

    @property
    def files(self) -> List[Path]:
        return [Path(self._slide._filename)]

    @property
    def transfer_syntax(self) -> Uid:
        """The uid of the transfer syntax of the image."""
        return self._encoder.transfer_syntax

    @property
    def photometric_interpretation(self) -> str:
        return self._encoder.photometric_interpretation(self.samples_per_pixel)

    @property
    def samples_per_pixel(self) -> int:
        return 3

    @property
    def focal_planes(self) -> List[float]:
        return [0.0]

    @property
    def optical_paths(self) -> List[str]:
        return ['0']

    @property
    def blank_color(self) -> Tuple[int, int, int]:
        return self._blank_color

    def close(self) -> None:
        """Close the open slide object, if not already closed."""
        try:
            self._slide.close()
        except ctypes.ArgumentError:
            # Slide already closed
            pass

    def _get_blank_color(
        self,
        photometric_interpretation: str
    ) -> Tuple[int, int, int]:
        """Return color to use blank tiles. Parses background color from
        openslide if present.

        Parameters
        ----------
        photometric_interpretation: str
            The photomoetric interpretation of the dataset

        Returns
        ----------
        Tuple[int, int, int]
            RGB color.

        """
        slide_background_color_string = self._slide.properties.get(
            PROPERTY_NAME_BACKGROUND_COLOR
        )
        if slide_background_color_string is not None:
            rgb = re.findall(
                r'([0-9a-fA-F]{2})',
                slide_background_color_string
            )
            if len(rgb) == 3:
                return (
                    int(rgb[0], 16),
                    int(rgb[1], 16),
                    int(rgb[2], 16)
                )
        return super()._get_blank_color(photometric_interpretation)


class OpenSlideAssociatedImageData(OpenSlideImageData):
    def __init__(
        self,
        open_slide: OpenSlide,
        image_type: OpenSlideAssociatedImageType,
        encoder: Encoder
    ):
        """Wraps a OpenSlide associated image (label or overview) to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        image_type: OpenSlideAssociatedImageType
            Type of image to wrap.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(open_slide, encoder)
        self._image_type = image_type
        if (
            image_type.value
            not in get_associated_image_names(self._slide._osr)
        ):
            raise ValueError(f"{image_type.value} not in {self._slide}")

        image = self._slide.associated_images[image_type.value]
        no_alpha = Image.new('RGB', image.size, self.blank_color)
        no_alpha.paste(image, mask=image.split()[3])
        self._image_size = Size.from_tuple(no_alpha.size)
        self._decoded_image = no_alpha
        self._encoded_image = self._encode(np.asarray(no_alpha))

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self.image_size

    @property
    def pixel_spacing(self) -> Optional[SizeMm]:
        """Size of the pixels in mm/pixel."""
        # TODO figure out pixel spacing for label and overview in openslide.
        return None

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
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._encoded_image

    def _get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> PILImage:
        if tile != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._decoded_image


class OpenSlideLevelImageData(OpenSlideImageData):
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
        self._slide = open_slide
        self._level_index = level_index
        self._image_size = Size.from_tuple(
            self._slide.level_dimensions[self._level_index]
        )
        self._downsample = int(
            self._slide.level_downsamples[self._level_index]
        )
        self._pyramid_index = int(math.log2(self.downsample))

        try:
            base_mpp_x = float(self._slide.properties[PROPERTY_NAME_MPP_X])
            base_mpp_y = float(self._slide.properties[PROPERTY_NAME_MPP_Y])
            self._pixel_spacing = SizeMm(
                base_mpp_x * self.downsample / 1000.0,
                base_mpp_y * self.downsample / 1000.0
            )
        except KeyError:
            raise Exception(
                "Could not determine pixel spacing as openslide did not "
                "provide mpp from the file."
            )

        # Get set image origin and size to bounds if available
        bounds_x = self._slide.properties.get(PROPERTY_NAME_BOUNDS_X, 0)
        bounds_y = self._slide.properties.get(PROPERTY_NAME_BOUNDS_Y, 0)
        bounds_w = self._slide.properties.get(PROPERTY_NAME_BOUNDS_WIDTH)
        bounds_h = self._slide.properties.get(PROPERTY_NAME_BOUNDS_HEIGHT)
        self._offset = Point(int(bounds_x), int(bounds_y))
        if bounds_w is not None and bounds_h is not None:
            self._image_size = (
                Size(int(bounds_w), int(bounds_h)) // self.downsample
            )
        else:
            self._image_size = Size.from_tuple(
                self._slide.level_dimensions[self._level_index]
            )

        self._blank_encoded_frame = bytes()
        self._blank_encoded_frame_size = None
        self._blank_decoded_frame = None
        self._blank_decoded_frame_size = None

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
    ) -> PILImage:
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
        PILImage
            Stitched image
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'focal plane {z}', str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f'optical path {path}', str(self))
        image_data = self._get_region(region)
        if image_data is None:
            image_data = self._get_blank_decoded_frame(region.size)
        return image_data

    def _detect_blank_tile(self, data: np.ndarray) -> bool:
        """Detect if tile data is a blank tile, i.e. either has full
        transparency or is filled with background color. First checks if the
        corners are transparent or has background color before checking whole
        data.

        Parameters
        ----------
        data: np.ndarray
            Data to check if blank.

        Returns
        ----------
        bool
            True if tile is blank.
        """

        TOP = RIGHT = -1
        BOTTOM = LEFT = 0
        CORNERS_Y = [BOTTOM, BOTTOM, TOP, TOP]
        CORNERS_X = [LEFT, RIGHT, LEFT, RIGHT]
        TRANSPARENCY = 3
        corners_transparency = np.ix_(CORNERS_X, CORNERS_Y, [TRANSPARENCY])
        if np.all(data[corners_transparency] == 0):
            if np.all(data[:, :, TRANSPARENCY] == 0):
                return True
        background = np.array(self.blank_color)
        corners_rgb = np.ix_(CORNERS_X, CORNERS_Y, range(TRANSPARENCY))
        if np.all(data[corners_rgb] == background):
            if np.all(data[:, :, 0:TRANSPARENCY] == background):
                return True
        return False

    def _get_blank_encoded_frame(self, size: Size) -> bytes:
        """Return cached blank encoded frame for size, or create frame if
        cached frame not available or of wrong size.

        Parameters
        ----------
        size: Size
            Size of frame to get.

        Returns
        ----------
        bytes
            Encoded blank frame.
        """
        if self._blank_encoded_frame_size != size:
            frame = np.full(
                size.to_tuple() + (3,),
                self.blank_color,
                dtype=np.dtype(np.uint8)
            )
            self._blank_encoded_frame = self._encode(frame)
            self._blank_encoded_frame_size = size
        return self._blank_encoded_frame

    def _get_blank_decoded_frame(self, size: Size) -> PILImage:
        """Return cached blank decoded frame for size, or create frame if
        cached frame not available or of wrong size.

        Parameters
        ----------
        size: Size
            Size of frame to get.

        Returns
        ----------
        bytes
            Decoded blank frame.
        """
        if (
            self._blank_decoded_frame is None
            or self._blank_decoded_frame_size != size
        ):
            frame = Image.new('RGB', size.to_tuple(), self.blank_color)
            self._blank_decoded_frame = frame
        return self._blank_decoded_frame

    def _get_region(
        self,
        region: Region
    ) -> Optional[PILImage]:
        """Return Image read from region in openslide image. If image data for
        region is blank, None is returned. Transparent pixels are made into
        background color

        Parameters
        ----------
        region: Region
            Region to get image for.

        Returns
        ----------
        Optional[PILImage]
            Image of region, or None if region is blank.
        """
        if region.size.width < 0 or region.size.height < 0:
            raise ValueError('Negative size not allowed')
        CHANNELS = 4
        TRANSPARENCY = 3

        location_in_base_level = region.start * self.downsample + self._offset

        region_data = np.empty(
            region.size.to_tuple() + (CHANNELS,),
            dtype=ctypes.c_uint8
        )

        _read_region(
            self._slide._osr,
            region_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
            location_in_base_level.x,
            location_in_base_level.y,
            self._level_index,
            region.size.width,
            region.size.height
        )
        region_data.shape = (region.size.height, region.size.width, CHANNELS)
        if self._detect_blank_tile(region_data):
            return None

        convert_argb_to_rgba(region_data.view(ctypes.c_uint32))

        image = Image.fromarray(region_data)
        no_alpha = Image.new('RGB', image.size, self.blank_color)
        no_alpha.paste(image, mask=image.split()[TRANSPARENCY])
        return no_alpha

    def _get_encoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str
    ) -> bytes:
        """Return image bytes for tile. Transparency is removed and tile is
        encoded as jpeg.

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
        bytes
            Tile bytes.
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'focal plane {z}', str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f'optical path {path}', str(self))
        tile = self._get_region(
            Region(tile_point*self.tile_size, self.tile_size)
        )
        if tile is None:
            return self._get_blank_encoded_frame(self.tile_size)
        return self._encode(np.asarray(tile))

    def _get_decoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str
    ) -> PILImage:
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
        PILImage
            Tile as Image.
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'focal plane {z}', str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f'optical path {path}', str(self))
        tile = self._get_region(
            Region(tile_point*self.tile_size, self.tile_size)
        )
        if tile is None:
            return self._get_blank_decoded_frame(self.tile_size)
        return tile


class OpenSlideDicomizer(BaseDicomizer):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: int,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        include_confidential: bool = True,
    ) -> None:
        self._slide = OpenSlide(filepath)
        self._pyramid_levels = self._get_pyramid_levels(self._slide)
        self._metadata = OpenSlideMetadata(self._slide)
        super().__init__(
            filepath,
            encoder,
            tile_size,
            modules,
            include_confidential
        )

    @property
    def has_label(self) -> bool:
        return (
            OpenSlideAssociatedImageType.LABEL.value
            in self._slide.associated_images
        )

    @property
    def has_overview(self) -> bool:
        return (
            OpenSlideAssociatedImageType.MACRO.value
            in self._slide.associated_images
        )

    @property
    def metadata(self) -> Metadata:
        return self._metadata

    @property
    def pyramid_levels(self) -> List[int]:
        return self._pyramid_levels

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by OpenSlide."""
        return OpenSlide.detect_format(str(filepath)) is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        return OpenSlideLevelImageData(
            self._slide,
            level_index,
            self._tile_size,
            self._encoder
        )

    def _create_label_image_data(self) -> DicomizerImageData:
        return OpenSlideAssociatedImageData(
            self._slide,
            OpenSlideAssociatedImageType.LABEL,
            self._encoder
        )

    def _create_overview_image_data(self) -> DicomizerImageData:
        return OpenSlideAssociatedImageData(
            self._slide,
            OpenSlideAssociatedImageType.MACRO,
            self._encoder
        )

    @staticmethod
    def _get_pyramid_levels(slide: OpenSlide) -> List[int]:
        """Return list of pyramid levels present in openslide slide."""
        return [
            int(math.log2(int(downsample)))
            for downsample in slide.level_downsamples
        ]
