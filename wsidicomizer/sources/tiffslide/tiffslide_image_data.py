#    Copyright 2023, 2025 SECTRA AB
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

import numpy as np
from PIL import Image as Pillow
from PIL.Image import Image
from tiffslide import TiffSlide
from wsidicom.codec import Encoder
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, Region, Size
from wsidicom.metadata import Image as ImageMetadata

from wsidicomizer.sources.openslide_like import OpenSlideLikeLevelImageData


class TiffSlideLevelImageData(OpenSlideLikeLevelImageData):
    def __init__(
        self,
        tiff_slide: TiffSlide,
        blank_color: int | tuple[int, int, int] | None,
        offset: Point | None,
        size: Size | None,
        image_metadata: ImageMetadata,
        level_index: int,
        tile_size: int | None,
        encoder: Encoder,
    ):
        """Wraps a TiffSlide level to ImageData.

        Parameters
        ----------
        tiff_slide: TiffSlide
            TiffSlide object to wrap.
        image_metadata: ImageMetadata
            Image metadata for image.
        level_index: int
            Level in TiffSlide object to wrap
        tile_size: int
            Output tile size.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(
            blank_color,
            offset,
            size,
            tiff_slide.level_dimensions,
            tiff_slide.level_downsamples,
            image_metadata,
            level_index,
            tile_size,
            encoder,
        )
        self._slide = tiff_slide
        axes = self._slide.properties["tiffslide.series-axes"]
        if axes == "YX":
            self._samples_per_pixel = 1
        else:
            self._samples_per_pixel = 3

    @property
    def samples_per_pixel(self) -> int:
        """Number of samples per pixel in the image."""
        return self._samples_per_pixel

    def read_region(self, region: Region, z: float, path: str) -> Image:
        """Read a pixel region directly from the tiffslide object.

        Parameters
        ----------
        region: Region
             Pixel region to read.
        z: float
            Z coordinate.
        path: str
            Optical path.

        Returns
        -------
        Image
            The region as a Pillow image.
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        image_data = self._get_region(region)
        if image_data is None:
            return self._get_blank_decoded_frame(region.size)
        return Pillow.fromarray(image_data)

    def _get_region(self, region: Region) -> np.ndarray | None:
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

        location_in_base_level = region.start * self._downsample + self._offset

        region_data = self._slide.read_region(
            location_in_base_level.to_tuple(),
            self._level_index,
            region.size.to_tuple(),
            as_array=True,
        )
        if self._detect_blank_tile(region_data):
            return None
        if self.samples_per_pixel == 1:
            region_data = region_data.squeeze(2)
        return region_data

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
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
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        decoded = self._get_region(Region(tile * self.tile_size, self.tile_size))
        if decoded is None:
            return self._get_blank_encoded_frame(self.tile_size)
        return self.encoder.encode(decoded)

    def get_decoded_tile(self, tile_point: Point, z: float, path: str) -> Image:
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
        return Pillow.fromarray(tile)

    def _detect_blank_tile2(self, data: np.ndarray) -> bool:
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
        return bool(
            np.all(data[corners_rgb] == background) and np.all(data == background)
        )
