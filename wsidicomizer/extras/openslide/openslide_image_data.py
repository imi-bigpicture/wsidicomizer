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

"""Image data for openslide compatible file."""

import ctypes
from enum import Enum
from typing import Optional, Tuple, Union

import numpy as np
from PIL import Image as Pillow
from PIL.Image import Image
from wsidicom.codec import Encoder
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, Region, Size
from wsidicom.metadata import Image as ImageMetadata

from wsidicomizer.config import settings
from wsidicomizer.extras.openslide.openslide import (
    OpenSlide,
    _read_region,
    convert_argb_to_rgba,
)
from wsidicomizer.sources.openslide_like import OpenSlideLikeLevelImageData

"""
OpenSlideImageData uses proteted functions from OpenSlide-Python to get image
data as numpy arrays instead of pillow images. The proteted function
_read_region is used to get raw data from the OpenSlide C API and argb2rgba is
used to convert argb to rgba. We consider this safe, as these directly map
to the Openslide C API and are thus not likely to change that often.
"""


class OpenSlideAssociatedImageType(Enum):
    LABEL = "label"
    MACRO = "macro"
    THUMBNAIL = "thumbnail"


class OpenSlideLevelImageData(OpenSlideLikeLevelImageData):
    def __init__(
        self,
        open_slide: OpenSlide,
        blank_color: Optional[Union[int, Tuple[int, int, int]]],
        offset: Optional[Point],
        size: Optional[Size],
        image_metadata: ImageMetadata,
        level_index: int,
        tile_size: Optional[int],
        encoder: Encoder,
    ):
        """Wraps a OpenSlide level to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        image_metadata: ImageMetadata
            Image metadata for image.
        level_index: int
            Level in OpenSlide object to wrap
        tile_size: int
            Output tile size.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(
            blank_color,
            offset,
            size,
            open_slide.level_dimensions,
            open_slide.level_downsamples,
            image_metadata,
            level_index,
            tile_size,
            encoder,
        )
        self._osr = open_slide._osr

    def stitch_tiles(self, region: Region, path: str, z: float, threads: int) -> Image:
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
        Image
            Stitched image
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        image_data = self._get_region(region)
        if image_data is None:
            return self._get_blank_decoded_frame(region.size)
        return image_data

    def _get_region(self, region: Region) -> Optional[Image]:
        """Return Image read from region in openslide image. If image data for
        region is blank, None is returned. Transparent pixels are made into
        background color

        Parameters
        ----------
        region: Region
            Region to get image for.

        Returns
        ----------
        Optional[Image]
            Image of region, or None if region is blank.
        """
        if region.size.width < 0 or region.size.height < 0:
            raise ValueError("Negative size not allowed")
        CHANNELS = 4
        TRANSPARENCY = 3

        location_in_base_level = region.start * self._downsample + self._offset

        region_data = np.empty(
            region.size.to_tuple() + (CHANNELS,), dtype=ctypes.c_uint8
        )
        try:
            _read_region(
                self._osr,
                region_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                location_in_base_level.x,
                location_in_base_level.y,
                self._level_index,
                region.size.width,
                region.size.height,
            )
        except Exception:
            if settings.fallback_to_blank_tile_on_error:
                return None
            raise
        region_data.shape = (region.size.height, region.size.width, CHANNELS)
        if self._detect_blank_tile(region_data):
            return None

        convert_argb_to_rgba(region_data.view(ctypes.c_uint32))  # type: ignore

        alpha_image = Pillow.fromarray(region_data)
        return self._remove_alpha(alpha_image)

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
        return self.encoder.encode(np.asarray(tile))

    def _get_decoded_tile(self, tile_point: Point, z: float, path: str) -> Image:
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
        Image
            Tile as Image.
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        tile = self._get_region(Region(tile_point * self.tile_size, self.tile_size))
        if tile is None:
            return self._get_blank_decoded_frame(self.tile_size)
        return tile

    def _detect_blank_tile(self, tile: np.ndarray) -> bool:
        """Detect if tile is a blank tile, i.e. either has full
        transparency or is filled with background color. First checks if the
        corners are transparent or has background color before checking whole
        tile.

        Parameters
        ----------
        tile: np.ndarray
            Tile to check if blank.

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
        if np.all(tile[corners_transparency] == 0):
            if np.all(tile[:, :, TRANSPARENCY] == 0):
                return True
        background = np.array(self.blank_color)
        corners_rgb = np.ix_(CORNERS_X, CORNERS_Y, range(TRANSPARENCY))
        if np.all(tile[corners_rgb] == background):
            if np.all(tile[:, :, 0:TRANSPARENCY] == background):
                return True
        return False
