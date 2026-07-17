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

from functools import cached_property

import numpy as np
from pydicom.uid import UID, JPEGBaseline8Bit
from wsidicom.codec import Encoder
from wsidicom.codec.decoder import ImageCodecsDecoder
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, PointMm, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem, ImageType

from isyntax import ISyntax
from wsidicomizer.image_data import PixelImageData


class ISyntaxLevelImageData(PixelImageData):
    def __init__(
        self,
        isyntax: ISyntax,
        image_metadata: ImageMetadata,
        tile_size: int | None,
        encoder: Encoder,
        level: int,
    ):
        super().__init__(encoder)
        self._slide = isyntax
        self._slide_level = isyntax.wsi.get_level(level)
        pixel_spacing = SizeMm(self._slide_level.mpp_x, self._slide_level.mpp_y) / 1000
        if (
            image_metadata.pixel_spacing is not None
            and image_metadata.pixel_spacing != pixel_spacing
        ):
            # Override pixel spacing
            self._pixel_spacing = image_metadata.pixel_spacing
        else:
            self._pixel_spacing = pixel_spacing
        self._file_tile_size = Size(self._slide.tile_width, self._slide.tile_height)
        if tile_size is None:
            self._tile_size = self._file_tile_size
        else:
            self._tile_size = Size(tile_size, tile_size)
        self._level = level
        self._image_coordinate_system = image_metadata.image_coordinate_system

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
    def focal_planes(self) -> list[float]:
        return [0.0]

    @property
    def optical_paths(self) -> list[str]:
        return ["1"]

    @property
    def blank_color(self) -> int | tuple[int, int, int]:
        return (255, 255, 255)

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        if self._image_coordinate_system is not None:
            return self._image_coordinate_system
        return ImageCoordinateSystem(origin=PointMm(25, 50), rotation=180)

    @property
    def thread_safe(self) -> bool:
        return False

    def read_region(self, region: Region, z: float, path: str) -> np.ndarray:
        """Read the pixels of a region directly from the ISyntax object.


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
        np.ndarray
            The region pixels.
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        image_data = self._get_region(region)
        if image_data is None:
            return self._get_blank_decoded_frame(region.size)
        return image_data

    def _get_region(self, region: Region) -> np.ndarray | None:
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

    def _get_tile(self, tile_point: Point, z: float, path: str) -> np.ndarray | None:
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

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return image bytes for tile.

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
        decoded = self._get_tile(tile, z, path)
        if decoded is None:
            return self._get_blank_encoded_frame(self.tile_size)
        return self.encoder.encode(decoded)

    def get_decoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str,
        cache: bool = True,
    ) -> np.ndarray:
        """Return the pixels of a tile.

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
        np.ndarray
            Tile pixels.
        """
        tile = self._get_tile(tile_point, z, path)
        if tile is None:
            return self._get_blank_decoded_frame(self.tile_size)
        return tile


class ISyntaxAssociatedImageImageData(PixelImageData):
    def __init__(
        self,
        frame: bytes,
        encoder: Encoder,
        image_type: ImageType,
        image_metadata: ImageMetadata | None = None,
        force_transcoding: bool = False,
    ):
        if image_type not in (ImageType.LABEL, ImageType.OVERVIEW):
            raise ValueError("image_type must be LABEL or OVERVIEW")
        super().__init__(encoder)
        self._frame = frame
        self._force_transcoding = force_transcoding
        if self._force_transcoding:
            self._transfer_syntax = self._encoder.transfer_syntax
        else:
            self._transfer_syntax = JPEGBaseline8Bit
        self._image_metadata = image_metadata
        self._image_type = image_type
        self._decoder = ImageCodecsDecoder(JPEGBaseline8Bit, "YBR_FULL_422")

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

    @cached_property
    def _decoded(self) -> np.ndarray:
        """Decode the associated image frame to a numpy array once."""
        return self._decoder.decode(self._frame)

    @property
    def image_size(self) -> Size:
        return Size(width=self._decoded.shape[1], height=self._decoded.shape[0])

    @property
    def tile_size(self) -> Size:
        return self.image_size

    @property
    def pixel_spacing(self) -> SizeMm | None:
        if self._image_metadata is None:
            return None
        return self._image_metadata.pixel_spacing

    @property
    def imaged_size(self) -> SizeMm | None:
        if self.pixel_spacing is not None:
            return self.pixel_spacing * self.image_size
        return None

    @property
    def samples_per_pixel(self) -> int:
        return 3

    @property
    def focal_planes(self) -> list[float]:
        return [0.0]

    @property
    def optical_paths(self) -> list[str]:
        return ["1"]

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        if (
            self._image_metadata is not None
            and self._image_metadata.image_coordinate_system is not None
        ):
            return self._image_metadata.image_coordinate_system
        if self._image_type == ImageType.LABEL:
            return ImageCoordinateSystem(origin=PointMm(0, 50), rotation=0)
        else:
            return ImageCoordinateSystem(origin=PointMm(25, 50), rotation=180)

    @property
    def thread_safe(self) -> bool:
        return True

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        if z not in self.focal_planes or path not in self.optical_paths:
            raise WsiDicomNotFoundError(
                f"focal plane {z} or optical path {path}", str(self)
            )
        if self._force_transcoding:
            return self.encoder.encode(self._decoded)
        return self._frame

    def get_decoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str,
        cache: bool = True,
    ) -> np.ndarray:
        return self._decoded

    def read_region(self, region: Region, z: float, path: str) -> np.ndarray:
        left, upper, right, lower = region.box
        return self._decoded[upper:lower, left:right]
