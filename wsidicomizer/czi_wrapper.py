import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import DefaultDict, Dict, List, Literal, Tuple

import numpy as np
import pydicom
from czifile import CziFile, DirectoryEntryDV
from PIL import Image
from pydicom.uid import UID as Uid
from turbojpeg import TJPF_RGB, TJSAMP_444, TurboJPEG
from wsidicom.geometry import Point, Region, Size, SizeMm

from wsidicomizer.imagedata_wrapper import ImageDataWrapper


class CziWrapper(ImageDataWrapper):
    _default_z = 0

    def __init__(
        self,
        filepath: str,
        tile_size: int,
        jpeg: TurboJPEG,
        jpeg_quality: Literal = 95,
        jpeg_subsample: Literal = TJSAMP_444
    ) -> None:
        super().__init__(jpeg, jpeg_quality, jpeg_subsample, TJPF_RGB)
        self._czi = CziFile(filepath)
        self._tile_size = Size(tile_size, tile_size)
        self._image_size = Size(self._czi.shape[4], self._czi.shape[3])
        self._image_origin = Point(self._czi.start[4], self._czi.start[3])
        self._block_directory = self._czi.filtered_subblock_directory
        self._tile_directory = self._create_tile_directory()
        self._blank_decoded_tile = Image.fromarray(self._create_blank_tile())
        self._blank_encoded_tile = self._encode(self._create_blank_tile())
        self._pixel_spacing = self._get_pixel_spacing()

    @property
    def pyramid_index(self) -> int:
        return 0

    @property
    def transfer_syntax(self) -> Uid:
        return pydicom.uid.JPEGBaseline8Bit

    @property
    def pixel_spacing(self) -> SizeMm:
        return self._pixel_spacing

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @property
    def tiled_size(self) -> Size:
        return self.image_size / self.tile_size

    @property
    def blank_decoded_tile(self) -> Image.Image:
        return self._blank_decoded_tile

    @property
    def blank_encoded_tile(self) -> bytes:
        return self._blank_encoded_tile

    @property
    def image_origin(self) -> Point:
        """Return coordinate of the top-left of the image."""
        return self._image_origin

    @property
    def block_directory(self) -> List[DirectoryEntryDV]:
        """Return list of DirectoryEntryDV sorted by mosaic index."""
        return self._block_directory

    @property
    def tile_directory(self) -> Dict[Point, List[int]]:
        """Return dict of tiles with mosaic indices."""
        return self._tile_directory

    def _get_pixel_spacing(self) -> SizeMm:
        """Get pixel spacing (mm per pixel) from metadata"""
        metadata = ET.fromstring(self._czi.metadata()).find('Metadata')
        scaling = metadata.find('Scaling')
        scaling_elements = scaling.find('Items')
        x: float = None
        y: float = None
        for distance in scaling_elements.findall('Distance'):
            dimension = distance.get('Id')
            # Value is in m per pixel, result in mm per pixel
            value = float(distance.find('Value').text) * pow(10, 6)
            if dimension == 'X':
                x = value
            elif dimension == 'Y':
                y = value
        if x is None or y is None:
            raise ValueError("Could not find pixel spacing in metadata")
        return SizeMm(x, y)

    def _create_blank_tile(self, fill: int = 255) -> np.ndarray:
        """Return blank tile in numpy format."""
        return np.full(
            self._size_to_numpy_shape(self.tile_size),
            fill,
            dtype=np.uint8
        )

    def _get_tile(self, tile: Point) -> np.ndarray:
        """Return tile data as numpy array for tile."""
        image_data = self._create_blank_tile()
        if tile not in self.tile_directory:
            # Should not happen (get_decoded_tile() and get_enoded_tile()
            # should already have checked).
            return image_data

        for block_index in self.tile_directory[tile]:
            # For each block covering the tile
            block = self._block_directory[block_index]
            block_data: np.ndarray = block.data_segment().data()
            block_start, block_size = self._get_block_start_and_size(block)
            block_data.shape = self._size_to_numpy_shape(block_size)

            block_end = block_start + block_size
            tile_start = tile * self.tile_size
            tile_end = (tile + 1) * self.tile_size

            # The block and tile both cover the region between these points
            tile_block_min_intersection = Point.max(tile_start, block_start)
            tile_block_max_intersection = Point.min(tile_end, block_end)

            # The intersects in relation to block and tile origin
            block_start_in_tile = tile_block_min_intersection - tile_start
            block_end_in_tile = tile_block_max_intersection - tile_start
            tile_start_in_block = tile_block_min_intersection - block_start
            tile_end_in_block = tile_block_max_intersection - block_start

            image_data[
                block_start_in_tile.y:block_end_in_tile.y,
                block_start_in_tile.x:block_end_in_tile.x,
                :
            ] = block_data[
                tile_start_in_block.y:tile_end_in_block.y,
                tile_start_in_block.x:tile_end_in_block.x,
                :
            ]
        return image_data

    def get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
        if tile not in self.tile_directory:
            return self.blank_decoded_tile
        return Image.fromarray(self._get_tile(tile))

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        if tile not in self.tile_directory:
            return self.blank_encoded_tile
        return self._encode(self._get_tile(tile))

    def close(self) -> None:
        """Close wrapped file."""
        self._czi.close()

    def _create_tile_directory(self) -> Dict[Point, List[int]]:
        """Create a directory mapping tile points to list of block indices that
        cover the tile."""
        tile_directory: DefaultDict[Point, List[int]] = defaultdict(list)

        for block_index, block in enumerate(self.block_directory):
            block_start, block_size = self._get_block_start_and_size(
                block
            )
            tile_region = Region.from_points(
                block_start // self.tile_size,
                (block_start+block_size) // self.tile_size
            )
            for tile in tile_region.iterate_all(include_end=True):
                tile_directory[tile].append(block_index)

        return dict(tile_directory)

    def _get_block_start_and_size(
        self,
        block: DirectoryEntryDV
    ) -> Tuple[Point, Size]:
        """Return start coordinate and size for block realtive to image
        origin."""
        for dimension_entry in block.dimension_entries:
            if dimension_entry.dimension == 'X':
                x_start = dimension_entry.start
                x_size = dimension_entry.size
            elif dimension_entry.dimension == 'Y':
                y_start = dimension_entry.start
                y_size = dimension_entry.size
        return (
            Point(x_start, y_start) - self.image_origin,
            Size(x_size, y_size)
        )

    @staticmethod
    def _size_to_numpy_shape(size: Size) -> Tuple[int, int, int]:
        return size.height, size.width, 3
