#    Copyright 2026 SECTRA AB
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

"""Image data for CZI files read by pylibCZIrw."""

from dataclasses import dataclass
from threading import RLock
from typing import Any

import numpy as np
from pydicom.uid import UID
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem

from wsidicomizer.image_data import PixelImageData

PIXEL_TYPES = {
    "Gray8": (1, np.dtype(np.uint8)),
    "Gray16": (1, np.dtype(np.uint16)),
    "Bgr24": (3, np.dtype(np.uint8)),
    "Bgr48": (3, np.dtype(np.uint16)),
}


@dataclass(frozen=True)
class CziRwLayout:
    x: int
    y: int
    width: int
    height: int
    channel_start: int
    channel_count: int
    z_start: int
    z_count: int
    pixel_type: str
    focal_planes: tuple[float, ...]
    zooms: tuple[float, ...]


class CziRwImageData(PixelImageData):
    def __init__(
        self,
        reader: Any,
        layout: CziRwLayout,
        encoder: Encoder,
        level_index: int,
        tile_size: int,
        read_lock: RLock,
        channel_to_index: dict[str, int],
        focal_plane_to_index: dict[float, int],
        image_metadata: ImageMetadata,
    ) -> None:
        super().__init__(encoder)
        self._reader = reader
        self._layout = layout
        self._level_index = level_index
        self._zoom = layout.zooms[level_index]
        self._tile_size = Size(tile_size, tile_size)
        self._read_lock = read_lock
        self._channel_to_index = channel_to_index
        self._focal_plane_to_index = focal_plane_to_index
        self._image_coordinate_system = image_metadata.image_coordinate_system
        self._pixel_spacing = image_metadata.pixel_spacing
        self._image_size = Size(
            int(layout.width * self._zoom), int(layout.height * self._zoom)
        )
        self._samples_per_pixel = PIXEL_TYPES[layout.pixel_type][0]
        self._focal_planes = sorted(focal_plane_to_index)
        self._optical_paths = list(channel_to_index)

    @property
    def transfer_syntax(self) -> UID:
        return self.encoder.transfer_syntax

    @property
    def image_size(self) -> Size:
        return self._image_size

    @property
    def tile_size(self) -> Size:
        return self._tile_size

    @property
    def pixel_spacing(self) -> SizeMm | None:
        if self._pixel_spacing is None:
            return None
        return self._pixel_spacing * (1 / self._zoom)

    @property
    def imaged_size(self) -> SizeMm | None:
        if self._pixel_spacing is None:
            return None
        return self._pixel_spacing * Size(self._layout.width, self._layout.height)

    @property
    def samples_per_pixel(self) -> int:
        return self._samples_per_pixel

    @property
    def photometric_interpretation(self) -> str:
        return self.encoder.photometric_interpretation

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem | None:
        return self._image_coordinate_system

    @property
    def thread_safe(self) -> bool:
        return True

    @property
    def focal_planes(self) -> list[float]:
        return self._focal_planes

    @property
    def optical_paths(self) -> list[str]:
        return self._optical_paths

    def get_decoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str,
        cache: bool = True,
    ) -> np.ndarray:
        x = tile_point.x * self.tile_size.width
        y = tile_point.y * self.tile_size.height
        width = min(self.tile_size.width, self.image_size.width - x)
        height = min(self.tile_size.height, self.image_size.height - y)
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError(f"CZI tile coordinate {tile_point} is outside the image.")
        pixels = self.read_region(Region(Point(x, y), Size(width, height)), z, path)
        if width == self.tile_size.width and height == self.tile_size.height:
            return pixels
        padded_shape = (self.tile_size.height, self.tile_size.width) + pixels.shape[2:]
        padded = np.zeros(padded_shape, dtype=pixels.dtype)
        padded[:height, :width] = pixels
        return padded

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        return self.encoder.encode(self.get_decoded_tile(tile, z, path))

    def read_region(self, region: Region, z: float, path: str) -> np.ndarray:
        if (
            region.start.x < 0
            or region.start.y < 0
            or region.start.x + region.size.width > self.image_size.width
            or region.start.y + region.size.height > self.image_size.height
        ):
            raise ValueError("CZI region is outside the image.")
        try:
            channel = self._channel_to_index[path]
            z_index = self._focal_plane_to_index[z]
        except KeyError as error:
            raise ValueError(
                f"Unknown CZI optical path or focal plane: {error}"
            ) from error

        x0, x1 = self._base_interval(
            region.start.x,
            region.size.width,
            self._layout.width,
            self._image_size.width,
        )
        y0, y1 = self._base_interval(
            region.start.y,
            region.size.height,
            self._layout.height,
            self._image_size.height,
        )
        roi = (
            self._layout.x + x0,
            self._layout.y + y0,
            x1 - x0,
            y1 - y0,
        )
        plane = {"C": channel, "Z": z_index}
        with self._read_lock:
            pixels = self._reader.read(
                roi=roi,
                plane=plane,
                zoom=self._zoom,
                pixel_type=self._layout.pixel_type,
            )
        if pixels.shape[:2] != (region.size.height, region.size.width):
            raise ValueError(
                "pylibCZIrw returned a CZI region with unexpected dimensions "
                f"{pixels.shape[:2]}."
            )
        if self._samples_per_pixel == 1:
            return pixels[..., 0] if pixels.ndim == 3 else pixels
        return pixels[..., ::-1]

    def _base_interval(
        self, start: int, length: int, base_extent: int, level_extent: int
    ) -> tuple[int, int]:
        end = start + length
        base_start = min(base_extent, round(start / self._zoom))
        base_end = (
            base_extent
            if end == level_extent
            else min(base_extent, round(end / self._zoom))
        )
        return base_start, base_end
