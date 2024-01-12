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
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

import numpy as np
from czifile import CziFile, DirectoryEntryDV
from PIL import Image as Pillow
from PIL.Image import Image
from pydicom.uid import UID as Uid
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata

from wsidicomizer.config import settings
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.sources.czi.czi_metadata import CziMetadata


@dataclass(frozen=True)
class CziBlock:
    index: int
    start: Point
    size: Size


class CziImageData(DicomizerImageData):
    def __init__(
        self,
        czi: CziFile,
        tile_size: int,
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
        self._czi._fh.lock = True
        self._dtype = self._czi.dtype
        super().__init__(encoder)
        self._tile_size = Size(tile_size, tile_size)
        assert isinstance(self._czi.filtered_subblock_directory, list)
        self._block_directory = self._czi.filtered_subblock_directory
        self._block_locks: Dict[int, Lock] = defaultdict(Lock)

        if self._merged_metadata.pixel_spacing is None:
            raise ValueError("Could not determine pixel spacing for czi image.")
        self._pixel_spacing = self._merged_metadata.pixel_spacing
        self._image_coordinate_system = merged_metadata.image_coordinate_system

    @property
    def pyramid_index(self) -> int:
        return 0

    @property
    def transfer_syntax(self) -> Uid:
        return self.encoder.transfer_syntax

    @cached_property
    def photometric_interpretation(self) -> str:
        return self.encoder.photometric_interpretation

    @property
    def pixel_spacing(self) -> SizeMm:
        return self._pixel_spacing

    @cached_property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return Size(self._get_size(axis="X"), self._get_size(axis="Y"))

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @cached_property
    def tiled_size(self) -> Size:
        return self.image_size.ceil_div(self.tile_size)

    @cached_property
    def focal_planes(self) -> List[float]:
        """Focal planes available in the image defined in um."""
        return sorted(self._czi_metadata.focal_plane_mapping)

    @property
    def optical_paths(self) -> List[str]:
        """Optical paths available in the image."""
        return self._czi_metadata.channel_mapping

    @cached_property
    def blank_decoded_tile(self) -> Image:
        return Pillow.fromarray(self._create_blank_tile())

    @cached_property
    def blank_encoded_tile(self) -> bytes:
        return self.encoder.encode(self._create_blank_tile())

    @cached_property
    def pixel_origin(self) -> Point:
        """Return coordinate of the top-left of the image."""
        return Point(self._get_start(axis="X"), self._get_start(axis="Y"))

    @cached_property
    def tile_directory(self) -> Dict[Tuple[Point, float, str], List[CziBlock]]:
        """Return dict of block, block start, and block size by tile position,
        focal plane and optical path

        Returns
        ----------
        Dict[Tuple[Point, float, str], Sequence[CziBlock]]:
            Directory of tile point, focal plane and channel as key and
            list of block, block start, and block size as item.
        """
        tile_directory: Dict[Tuple[Point, float, str], List[CziBlock]] = defaultdict(
            list
        )
        assert isinstance(self._czi.filtered_subblock_directory, list)
        for index, block in enumerate(self._czi.filtered_subblock_directory):
            block_start, block_size, z, c = self._get_block_dimensions(block)
            tile_region = Region.from_points(
                block_start // self.tile_size,
                (block_start + block_size) // self.tile_size,
            )
            for tile in tile_region.iterate_all():
                tile_directory[tile, z, c].append(
                    CziBlock(index, block_start, block_size)
                )

        return tile_directory

    @cached_property
    def samples_per_pixel(self) -> int:
        return self._get_size(axis="0")

    @property
    def block_directory(self) -> List[DirectoryEntryDV]:
        return self._block_directory

    @staticmethod
    def detect_format(filepath: Path) -> Optional[str]:
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
        image_data = self._create_blank_tile()
        if (tile_point, z, path) not in self.tile_directory:
            # Should not happen (get_decoded_tile() and get_enoded_tile()
            # should already have checked).
            return image_data

        for block in self.tile_directory[tile_point, z, path]:
            # For each block covering the tile

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

    def _get_decoded_tile(self, tile: Point, z: float, path: str) -> Image:
        """Return Image for tile.

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
        Image
            Tile as Image.
        """
        if (tile, z, path) not in self.tile_directory:
            return self.blank_decoded_tile
        return Pillow.fromarray(self._get_tile(tile, z, path))

    def _get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
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

    def _get_size(self, axis: str) -> int:
        index = self._get_axis_index(axis)
        assert isinstance(self._czi.shape, tuple)
        return self._czi.shape[index]

    def _get_start(self, axis: str) -> int:
        index = self._get_axis_index(axis)
        assert isinstance(self._czi.start, tuple)
        return self._czi.start[index]

    def _get_axis_index(self, axis: str) -> int:
        index = str(self._czi.axes).index(axis.capitalize())
        if not index >= 0:
            raise ValueError(f"Axis {axis} not found in axes {self._czi.axes}")
        return index

    def _create_blank_tile(self) -> np.ndarray:
        """Return blank tile in numpy array.

        Returns
        ----------
        np.ndarray
            A blank tile as numpy array.
        """
        if self.photometric_interpretation == "MONOCHROME2":
            fill_value = 0
        else:
            fill_value = 1
        assert isinstance(self._czi.dtype, np.dtype)
        return np.full(
            self._size_to_numpy_shape(self.tile_size),
            fill_value * np.iinfo(self._czi.dtype).max,
            dtype=np.dtype(self._czi.dtype),
        )

    @lru_cache(settings.czi_block_cache_size)
    def _get_tile_data(self, block_index: int) -> np.ndarray:
        """Get decompressed tile data from czi file. Cache the tile data. To
        prevent multiple threads proceseing the same tile, use a lock for
        each block."""
        block_lock = self._block_locks[block_index]
        if block_lock.locked():
            # Another thread is already reading the block. Wait for lock and
            # read from cache.
            with block_lock:
                return self._get_tile_data(block_index)

        with block_lock:
            # Lock block and read from block.
            block = self.block_directory[block_index]
            data = block.data_segment().data()
            return data

    def _get_block_dimensions(
        self, block: DirectoryEntryDV
    ) -> Tuple[Point, Size, float, str]:
        """Return start coordinate and size for block relative to image
        origin and block focal plane and optical path.

        Parameters
        ----------
        block: DirectoryEntryDV
            Block to get start and size from.

        Returns
        ----------
        Tuple[Point, Size]
            Start point coordinate, size, focal plane and optical path for
            block.
        """
        x_start: Optional[int] = None
        x_size: Optional[int] = None
        y_start: Optional[int] = None
        y_size: Optional[int] = None
        z = 0.0
        c = "0"

        for dimension_entry in block.dimension_entries:
            if dimension_entry.dimension == "X":
                x_start = dimension_entry.start
                x_size = dimension_entry.size
            elif dimension_entry.dimension == "Y":
                y_start = dimension_entry.start
                y_size = dimension_entry.size
            elif dimension_entry.dimension == "Z":
                z = self._czi_metadata.focal_plane_mapping[dimension_entry.start]
            elif dimension_entry.dimension == "C":
                c = self._czi_metadata.channel_mapping[dimension_entry.start]

        if x_start is None or x_size is None or y_start is None or y_size is None:
            raise ValueError("Could not determine position of block.")

        return (Point(x_start, y_start) - self.pixel_origin, Size(x_size, y_size), z, c)

    def _size_to_numpy_shape(self, size: Size) -> Tuple[int, ...]:
        """Return a tuple for use with numpy.shape."""
        if self.samples_per_pixel == 1:
            return size.height, size.width
        return size.height, size.width, self.samples_per_pixel
