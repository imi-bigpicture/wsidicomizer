#    Copyright 2023 SECTRA AB
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

"""Image data for tiffslide compatible file."""

import math
import re
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image
from PIL.Image import Image as PILImage
from pydicom.uid import UID as Uid
from tiffslide import TiffSlide
from tiffslide.tiffslide import (
    PROPERTY_NAME_BACKGROUND_COLOR,
    PROPERTY_NAME_BOUNDS_HEIGHT,
    PROPERTY_NAME_BOUNDS_WIDTH,
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    PROPERTY_NAME_MPP_X,
    PROPERTY_NAME_MPP_Y,
)
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Orientation, Point, PointMm, Region, Size, SizeMm
from wsidicom.instance import ImageCoordinateSystem

from wsidicomizer.encoding import Encoder
from wsidicomizer.image_data import DicomizerImageData


class TiffSlideAssociatedImageType(Enum):
    LABEL = "label"
    MACRO = "macro"


class TiffSlideImageData(DicomizerImageData):
    def __init__(self, tiff_slide: TiffSlide, encoder: Encoder):
        """Wraps a TiffSlide image to ImageData.

        Parameters
        ----------
        tiff_slide: TiffSlide
            TiffSlide object to wrap.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(encoder)
        self._slide = tiff_slide
        self._blank_color = self._get_blank_color(self.photometric_interpretation)

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
        return ["0"]

    @property
    def blank_color(self) -> Tuple[int, int, int]:
        return self._blank_color

    def _get_blank_color(self, photometric_interpretation: str) -> Tuple[int, int, int]:
        """Return color to use blank tiles. Parses background color from
        tiffslide if present.

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
            rgb = re.findall(r"([0-9a-fA-F]{2})", slide_background_color_string)
            if len(rgb) == 3:
                return (int(rgb[0], 16), int(rgb[1], 16), int(rgb[2], 16))
        return super()._get_blank_color(photometric_interpretation)


class TiffSlideAssociatedImageData(TiffSlideImageData):
    def __init__(
        self,
        tiff_slide: TiffSlide,
        image_type: TiffSlideAssociatedImageType,
        encoder: Encoder,
    ):
        """Wraps a TiffSlide associated image (label or overview) to ImageData.

        Parameters
        ----------
        tiff_slide: TiffSlide
            TiffSlide object to wrap.
        image_type: TiffSlideAssociatedImageType
            Type of image to wrap.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(tiff_slide, encoder)
        self._image_type = image_type
        if image_type.value not in self._slide.associated_images:
            raise ValueError(f"{image_type.value} not in {self._slide}")

        image = self._slide.associated_images[image_type.value]
        self._image_size = Size.from_tuple(image.size)
        self._decoded_image = image
        self._encoded_image = self._encode(np.asarray(image))

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
        return None

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return 0

    def _get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        if tile != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._encoded_image

    def _get_decoded_tile(self, tile: Point, z: float, path: str) -> PILImage:
        if tile != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._decoded_image


class TiffSlideLevelImageData(TiffSlideImageData):
    def __init__(
        self, tiff_slide: TiffSlide, level_index: int, tile_size: int, encoder: Encoder
    ):
        super().__init__(tiff_slide, encoder)
        """Wraps a TiffSlide level to ImageData.

        Parameters
        ----------
        tiff_slide: TiffSlide
            TiffSlide object to wrap.
        level_index: int
            Level in TiffSlide object to wrap
        tile_size: int
            Output tile size.
        encoded: Encoder
            Encoder to use.
        """
        self._tile_size = Size(tile_size, tile_size)
        self._slide = tiff_slide
        self._level_index = level_index
        self._image_size = Size.from_tuple(
            self._slide.level_dimensions[self._level_index]
        )
        self._downsample = self._slide.level_downsamples[self._level_index]
        self._pyramid_index = int(round(math.log2(self.downsample)))
        try:
            base_mpp_x = float(self._slide.properties[PROPERTY_NAME_MPP_X])
            base_mpp_y = float(self._slide.properties[PROPERTY_NAME_MPP_Y])
            self._pixel_spacing = SizeMm(
                base_mpp_x * self.downsample / 1000.0,
                base_mpp_y * self.downsample / 1000.0,
            )
        except KeyError:
            raise Exception(
                "Could not determine pixel spacing as tiffslide did not "
                "provide mpp from the file."
            )

        # Get set image origin and size to bounds if available
        bounds_x = self._slide.properties.get(PROPERTY_NAME_BOUNDS_X)
        bounds_y = self._slide.properties.get(PROPERTY_NAME_BOUNDS_Y)
        bounds_w = self._slide.properties.get(PROPERTY_NAME_BOUNDS_WIDTH)
        bounds_h = self._slide.properties.get(PROPERTY_NAME_BOUNDS_HEIGHT)
        if bounds_x is not None and bounds_y is not None:
            self._offset = Point(int(bounds_x), int(bounds_y))
        else:
            self._offset = Point(0, 0)
        if bounds_w is not None and bounds_h is not None:
            self._image_size = Size(int(bounds_w), int(bounds_h)) // int(
                round(self.downsample)
            )
        else:
            self._image_size = Size.from_tuple(
                self._slide.level_dimensions[self._level_index]
            )

        self._blank_encoded_frame = bytes()
        self._blank_encoded_frame_size = None
        self._blank_decoded_frame = None
        self._blank_decoded_frame_size = None
        self._image_coordinate_system = ImageCoordinateSystem(
            PointMm(
                self._offset.x * base_mpp_x / 1000, self._offset.y * base_mpp_y / 1000
            ),
            Orientation((0, 1, 0, 1, 0, 0)),
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
    def downsample(self) -> float:
        """Downsample facator for level."""
        return self._downsample

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return self._pyramid_index

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        return self._image_coordinate_system

    def stitch_tiles(
        self, region: Region, path: str, z: float, threads: int
    ) -> PILImage:
        """Overrides ImageData stitch_tiles() to read reagion directly from
        tiffslide object.

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
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        image_data = self._get_region(region)
        if image_data is None:
            image_data = self._get_blank_decoded_frame(region.size)
        return Image.fromarray(image_data)

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
        background = np.array(self.blank_color)
        corners_rgb = np.ix_(CORNERS_X, CORNERS_Y)
        if np.all(data[corners_rgb] == background):
            if np.all(data == background):
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
                size.to_tuple() + (3,), self.blank_color, dtype=np.dtype(np.uint8)
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
        if self._blank_decoded_frame is None or self._blank_decoded_frame_size != size:
            frame = Image.new("RGB", size.to_tuple(), self.blank_color)
            self._blank_decoded_frame = frame
        return self._blank_decoded_frame

    def _get_region(self, region: Region) -> Optional[np.ndarray]:
        """Return Image read from region in tiffslide image. If image data for
        region is blank, None is returned. Transparent pixels are made into
        background color

        Parameters
        ----------
        region: Region
            Region to get image for.

        Returns
        ----------
        Optional[np.ndarray]
            Image data of region, or None if region is blank.
        """
        if region.size.width < 0 or region.size.height < 0:
            raise ValueError("Negative size not allowed")

        location_in_base_level = region.start * self.downsample + self._offset

        region_data = self._slide.read_region(
            location_in_base_level.to_tuple(),
            self._level_index,
            region.size.to_tuple(),
            as_array=True,
        )
        if self._detect_blank_tile(region_data):
            return None

        return region_data

    def _get_encoded_tile(self, tile_point: Point, z: float, path: str) -> bytes:
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
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        tile = self._get_region(Region(tile_point * self.tile_size, self.tile_size))
        if tile is None:
            return self._get_blank_encoded_frame(self.tile_size)
        return self._encode(tile)

    def _get_decoded_tile(self, tile_point: Point, z: float, path: str) -> PILImage:
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
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        tile = self._get_region(Region(tile_point * self.tile_size, self.tile_size))
        if tile is None:
            return self._get_blank_decoded_frame(self.tile_size)
        return Image.fromarray(tile)
