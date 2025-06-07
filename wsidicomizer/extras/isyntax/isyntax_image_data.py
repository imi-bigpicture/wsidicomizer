#    Copyright 2024 SECTRA AB
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

"""Image data for pyisintax compatible file."""

from io import BytesIO
from typing import List, Optional, Tuple, Union

import numpy as np
from PIL import Image as Pillow
from PIL.Image import Image
from pydicom.uid import UID, JPEGBaseline8Bit
from wsidicom.codec import Encoder
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, PointMm, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem

from isyntax import ISyntax
from wsidicomizer.image_data import DicomizerImageData


class ISyntaxLevelImageData(DicomizerImageData):
    def __init__(
        self,
        isyntax: ISyntax,
        merged_metadata: ImageMetadata,
        tile_size: Optional[int],
        encoder: Encoder,
        level: int,
    ):
        super().__init__(encoder)
        self._slide = isyntax
        self._slide_level = isyntax.wsi.get_level(level)
        pixel_spacing = SizeMm(self._slide_level.mpp_x, self._slide_level.mpp_y) / 1000
        if (
            merged_metadata.pixel_spacing is not None
            and merged_metadata.pixel_spacing != pixel_spacing
        ):
            # Override pixel spacing
            self._pixel_spacing = merged_metadata.pixel_spacing
        else:
            self._pixel_spacing = pixel_spacing
        self._file_tile_size = Size(self._slide.tile_width, self._slide.tile_height)
        if tile_size is None:
            self._tile_size = self._file_tile_size
        else:
            self._tile_size = Size(tile_size, tile_size)
        self._level = level

    @property
    def image_size(self) -> Size:
        return Size(self._slide_level.width, self._slide_level.height)

    @property
    def tile_size(self) -> Size:
        return self._tile_size

    @property
    def file_tile_size(self) -> Size:
        return self._file_tile_size

    @property
    def pixel_spacing(self) -> SizeMm:
        return self._pixel_spacing

    @property
    def imaged_size(self) -> SizeMm:
        return self.pixel_spacing * self.image_size

    @property
    def downsample(self) -> float:
        return self._slide_level.scale

    @property
    def transfer_syntax(self) -> UID:
        """The uid of the transfer syntax of the image."""
        return self.encoder.transfer_syntax

    @property
    def photometric_interpretation(self) -> str:
        return self.encoder.photometric_interpretation

    @property
    def samples_per_pixel(self) -> int:
        return self.encoder.samples_per_pixel

    @property
    def focal_planes(self) -> List[float]:
        return [0.0]

    @property
    def optical_paths(self) -> List[str]:
        return ["0"]

    @property
    def blank_color(self) -> Union[int, Tuple[int, int, int]]:
        return (255, 255, 255)

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        return ImageCoordinateSystem(PointMm(0, 0), 0)

    @property
    def thread_safe(selt) -> bool:
        return False

    def stitch_tiles(self, region: Region, path: str, z: float, threads: int) -> Image:
        """Overrides ImageData stitch_tiles() to read reagion directly from
        ISyntax object.

        Parameters
        ----------
        region: Region
             Pixel region to stitch to image
        path: str
            Optical path
        z: float
            Z coordinate
        threads: int
            Threads to use for stiching, not used in this implementation.

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
        return Pillow.fromarray(image_data)

    def _get_region(self, region: Region) -> Optional[np.ndarray]:
        """Return Image read from region in ISyntax image. If image data for
        region is blank, None is returned.

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

        region_data = self._slide.read_region(
            region.start.x,
            region.start.y,
            region.size.width,
            region.size.height,
            self._level,
        )[:, :, :3]
        if self._detect_blank_tile(region_data):
            return None
        return region_data

    def _get_tile(self, tile_point: Point, z: float, path: str) -> Optional[np.ndarray]:
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        if self._tile_size == self.file_tile_size:
            tile = self._slide.read_tile(tile_point.x, tile_point.y, self._level)[
                :, :, :3
            ]
        else:
            tile = self._slide.read_region(
                tile_point.x * self._tile_size.width,
                tile_point.y * self._tile_size.height,
                self._tile_size.width,
                self._tile_size.height,
                self._level,
            )[:, :, :3]
        if self._detect_blank_tile(tile):
            return None
        return tile

    def _get_encoded_tile(self, tile_point: Point, z: float, path: str) -> bytes:
        """Return image bytes for tile.

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
        tile = self._get_tile(tile_point, z, path)
        if tile is None:
            return self._get_blank_encoded_frame(self.tile_size)
        return self.encoder.encode(tile)

    def _get_decoded_tile(self, tile_point: Point, z: float, path: str) -> Image:
        """Return Image for tile.

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
        tile = self._get_tile(tile_point, z, path)
        if tile is None:
            return self._get_blank_decoded_frame(self.tile_size)
        return Pillow.fromarray(tile)


class ISyntaxAssociatedImageImageData(DicomizerImageData):
    def __init__(
        self,
        frame: bytes,
        encoder: Encoder,
        force_transcoding: bool = False,
    ):
        super().__init__(encoder)
        self._frame = frame
        self._force_transcoding = force_transcoding
        if self._force_transcoding:
            self._transfer_syntax = self._encoder.transfer_syntax
        else:
            self._transfer_syntax = JPEGBaseline8Bit

    @property
    def transfer_syntax(self) -> UID:
        if self._force_transcoding:
            return self._encoder.transfer_syntax
        return JPEGBaseline8Bit

    @property
    def photometric_interpretation(self) -> str:
        if self._force_transcoding:
            return self.encoder.photometric_interpretation
        return "YBR_FULL_422"

    @property
    def image(self) -> Image:
        return Pillow.open(BytesIO(self._frame))

    @property
    def image_size(self) -> Size:
        return Size(self.image.width, self.image.height)

    @property
    def tile_size(self) -> Size:
        return self.image_size

    @property
    def pixel_spacing(self) -> Optional[SizeMm]:
        return None

    @property
    def imaged_size(self) -> Optional[SizeMm]:
        return None

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
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        return ImageCoordinateSystem(PointMm(0, 0), 0)

    @property
    def thread_safe(self) -> bool:
        return True

    def _get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        if z not in self.focal_planes or path not in self.optical_paths:
            raise WsiDicomNotFoundError(
                f"focal plane {z} or optical path {path}", str(self)
            )
        if self._force_transcoding:
            return self.encoder.encode(self.image)
        return self._frame

    def _get_decoded_tile(self, tile: Point, z: float, path: str) -> Image:
        return self.image
