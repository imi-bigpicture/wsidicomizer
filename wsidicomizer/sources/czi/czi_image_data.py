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

"""Image data for czi file."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from threading import RLock

import numpy as np
from czifile import CziDirectoryEntryDV, CziFile, CziSubBlockSegmentData
from PIL import Image as Pillow
from PIL.Image import Image
from pydicom.uid import UID
from wsidicom.cache import lru_cached_method
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem

from wsidicomizer.config import settings
from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.sources.czi.czi_metadata import CziMetadata


@dataclass(frozen=True)
class CziBlock:
    index: int
    start: Point
    size: Size


class CziImageData(BaseDicomizerImageData):
    def __init__(
        self,
        czi: CziFile,
        tile_size: int | None,
        encoder: Encoder,
        czi_metadata: CziMetadata,
        merged_metadata: ImageMetadata,
    ) -> None:
        """Wraps a czi file to ImageData. Multiple pyramid levels are currently
        not supported.

        Parameters
        ----------
        filepath: str
            Path to czi file to wrap.
        tile_size: int
            Output tile size.
        encoded: Encoder
            Encoded to use.
        czi_metadata: CziMetadata
            Czi metadata to use.
        merged_metadata: ImageMetadata
            Merged image metadata to use.
        """
        self._czi = czi
        self._czi_metadata = czi_metadata
        self._merged_metadata = merged_metadata

        assert self._merged_metadata.pixel_spacing is not None
        self._czi.set_lock(True)
        super().__init__(encoder)
        if tile_size is None:
            tile_size = settings.default_tile_size
        self._tile_size = Size(tile_size, tile_size)
        self._block_directory = self._czi.filtered_subblock_directory
        self._dtype = np.dtype(self._block_directory[0].dtype)
        self._block_locks: dict[int, RLock] = defaultdict(RLock)

        if self._merged_metadata.pixel_spacing is None:
            raise ValueError("Could not determine pixel spacing for czi level image.")
        self._pixel_spacing = self._merged_metadata.pixel_spacing
        self._image_coordinate_system = merged_metadata.image_coordinate_system
        self._image_size = Size(self._get_size(axis="X"), self._get_size(axis="Y"))
        self._tiled_size = self.image_size.ceil_div(self.tile_size)
        self._focal_planes = sorted(self._czi_metadata.focal_plane_mapping)
        self._samples_per_pixel = self._get_size(axis="S")

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem | None:
        return self._image_coordinate_system

    @property
    def transfer_syntax(self) -> UID:
        return self.encoder.transfer_syntax

    @property
    def photometric_interpretation(self) -> str:
        return self.encoder.photometric_interpretation

    @property
    def pixel_spacing(self) -> SizeMm:
        return self._pixel_spacing

    @property
    def imaged_size(self) -> SizeMm:
        return self._pixel_spacing * self.image_size

    @property
    def thread_safe(self) -> bool:
        return True

    @property
    def image_size(self) -> Size:  # pyright: ignore[reportIncompatibleMethodOverride]
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @property
    def tiled_size(self) -> Size:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self._tiled_size

    @property
    def focal_planes(self) -> list[float]:
        """Focal planes available in the image defined in um."""
        return self._focal_planes

    @property
    def optical_paths(self) -> list[str]:
        """Optical paths available in the image."""
        return self._czi_metadata.channel_mapping

    @cached_property
    def blank_decoded_tile(self) -> Image:
        return Pillow.fromarray(self._create_blank_tile_array())

    @cached_property
    def blank_encoded_tile(self) -> bytes:
        return self.encoder.encode(self._create_blank_tile_array())

    @cached_property
    def pixel_origin(self) -> Point:
        """Return coordinate of the top-left of the image."""
        return Point(self._get_start(axis="X"), self._get_start(axis="Y"))

    @cached_property
    def tile_directory(self) -> dict[tuple[Point, float, str], list[CziBlock]]:
        """Return dict of block, block start, and block size by tile position,
        focal plane and optical path

        Returns
        ----------
        Dict[Tuple[Point, float, str], Sequence[CziBlock]]:
            Directory of tile point, focal plane and channel as key and
            list of block, block start, and block size as item.
        """
        tile_directory: dict[tuple[Point, float, str], list[CziBlock]] = defaultdict(
            list
        )
        for index, block in enumerate(self._block_directory):
            block_start, block_size, z, c = self._get_block_dimensions(block)
            tile_region = Region.from_points(
                block_start // self.tile_size,
                (block_start + block_size).ceil_div(self.tile_size),
            )
            for tile in tile_region.iterate_all():
                tile_directory[tile, z, c].append(
                    CziBlock(index, block_start, block_size)
                )

        return tile_directory

    @property
    def samples_per_pixel(self) -> int:
        return self._samples_per_pixel

    @property
    def block_directory(self) -> Sequence[CziDirectoryEntryDV]:
        return self._block_directory

    @staticmethod
    def detect_format(filepath: Path) -> str | None:
        try:
            with CziFile(filepath):
                return "czi"
        except ValueError:
            return None

    def _get_tile(self, tile_point: Point, z: float, path: str) -> np.ndarray:
        """Return tile data as numpy array for tile.

        Parameters
        ----------
        tile_point: Point
            Tile coordinate to get.

        Returns
        ----------
        np.ndarray
            Tile as numpy array.
        """
        # A blank tile to paste blocks into
        image_data = self._create_blank_tile_array()
        if (tile_point, z, path) not in self.tile_directory:
            # Should not happen (get_decoded_tile() and get_enoded_tile()
            # should already have checked).
            return image_data

        # For each block covering the tile
        for block in self.tile_directory[tile_point, z, path]:
            # Start and end coordinates for block and tile
            block_end = block.start + block.size
            tile_start = tile_point * self.tile_size
            tile_end = (tile_point + 1) * self.tile_size

            # The block and tile both cover the region between these points
            tile_block_start_intersection = Point.max(tile_start, block.start)
            tile_block_end_intersection = Point.min(tile_end, block_end)

            # The intersects in relation to block and tile origin
            block_start_in_tile = tile_block_start_intersection - tile_start
            block_end_in_tile = tile_block_end_intersection - tile_start
            tile_start_in_block = tile_block_start_intersection - block.start
            tile_end_in_block = tile_block_end_intersection - block.start

            # Get decompressed data
            block_data = self._get_tile_data(block.index)
            # Reshape the block data to remove leading 1-indices.
            block_data.shape = self._size_to_numpy_shape(block.size)
            # Paste in block data into tile.
            image_data[
                block_start_in_tile.y : block_end_in_tile.y,
                block_start_in_tile.x : block_end_in_tile.x,
            ] = block_data[
                tile_start_in_block.y : tile_end_in_block.y,
                tile_start_in_block.x : tile_end_in_block.x,
            ]
        return image_data

    def get_decoded_tile(self, tile_point: Point, z: float, path: str) -> Image:
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
        if (tile_point, z, path) not in self.tile_directory:
            return self.blank_decoded_tile
        return Pillow.fromarray(self._get_tile(tile_point, z, path))

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return image bytes for tile. Tile is encoded as jpeg.

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
        if (tile, z, path) not in self.tile_directory:
            return self.blank_encoded_tile
        frame = self._get_tile(tile, z, path)
        return self.encoder.encode(frame)

    @staticmethod
    def _block_axis(block: CziDirectoryEntryDV, axis: str) -> tuple[int, int] | None:
        """Return (start, size) of block along axis, or None if axis is absent."""
        if axis not in block.dims:
            return None
        index = block.dims.index(axis)
        return block.start[index], block.shape[index]

    @classmethod
    def detect_pixel_format(cls, czi: CziFile) -> tuple[int, np.dtype]:
        """Return (samples_per_pixel, dtype) for a czi without building the
        instance, so a source can pick a matching default encoder."""
        directory = czi.filtered_subblock_directory
        dtype = np.dtype(directory[0].dtype)
        spans = [
            span
            for block in directory
            if (span := cls._block_axis(block, "S")) is not None
        ]
        samples_per_pixel = (
            1
            if not spans
            else max(start + size for start, size in spans)
            - min(start for start, _ in spans)
        )
        return samples_per_pixel, dtype

    def _get_size(self, axis: str) -> int:
        """Full image size along axis, derived from the subblock directory."""
        spans = [
            span
            for block in self._block_directory
            if (span := self._block_axis(block, axis)) is not None
        ]
        if not spans:
            return 1
        return max(start + size for start, size in spans) - min(
            start for start, _ in spans
        )

    def _get_start(self, axis: str) -> int:
        """Origin of the image along axis (lowest block start)."""
        starts = [
            span[0]
            for block in self._block_directory
            if (span := self._block_axis(block, axis)) is not None
        ]
        return min(starts) if starts else 0

    def _create_blank_tile_array(self) -> np.ndarray:
        """Return blank tile in numpy array.

        Returns
        ----------
        np.ndarray
            A blank tile as numpy array.
        """
        fill_value = 0 if self.photometric_interpretation == "MONOCHROME2" else 1
        return np.full(
            self._size_to_numpy_shape(self.tile_size),
            fill_value * np.iinfo(self._dtype).max,
            dtype=self._dtype,
        )

    @lru_cached_method(maxsize=lambda: settings.czi_block_cache_size)
    def _get_tile_data(self, block_index: int) -> np.ndarray:
        """Get decompressed tile data from czi file. Cache the tile data. To
        prevent multiple threads proceseing the same tile, use a lock for
        each block."""
        block_lock = self._block_locks[block_index]
        acquired = False
        try:
            # Try to lock block.
            acquired = block_lock.acquire(blocking=False)
            if not acquired:
                # Another thread is already reading the block.
                # Wait for lock and hopefully read from cache.
                acquired = block_lock.acquire(blocking=True)
                return self._get_tile_data(block_index)
            else:
                # Read the block data.
                block = self.block_directory[block_index]
                segment = block.read_segment_data(self._czi)
                assert isinstance(segment, CziSubBlockSegmentData)
                return segment.data()
        finally:
            if acquired:
                block_lock.release()

    def _get_block_dimensions(
        self, block: CziDirectoryEntryDV
    ) -> tuple[Point, Size, float, str]:
        """Return start coordinate and size for block relative to image
        origin and block focal plane and optical path.

        Parameters
        ----------
        block: CziDirectoryEntryDV
            Block to get start and size from.

        Returns
        ----------
        Tuple[Point, Size]
            Start point coordinate, size, focal plane and optical path for
            block.
        """
        x_start: int | None = None
        x_size: int | None = None
        y_start: int | None = None
        y_size: int | None = None
        z = 0.0
        c = "1"

        for dimension, start, size in zip(
            block.dims, block.start, block.shape, strict=True
        ):
            if dimension == "X":
                x_start = start
                x_size = size
            elif dimension == "Y":
                y_start = start
                y_size = size
            elif dimension == "Z":
                z = self._czi_metadata.focal_plane_mapping[start]
            elif dimension == "C":
                c = self._czi_metadata.channel_mapping[start]

        if x_start is None or x_size is None or y_start is None or y_size is None:
            raise ValueError("Could not determine position of block.")

        return (Point(x_start, y_start) - self.pixel_origin, Size(x_size, y_size), z, c)

    def _size_to_numpy_shape(self, size: Size) -> tuple[int, ...]:
        """Return a tuple for use with numpy.shape."""
        if self.samples_per_pixel == 1:
            return size.height, size.width
        return size.height, size.width, self.samples_per_pixel
