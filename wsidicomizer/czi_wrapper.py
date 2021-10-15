import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import DefaultDict, Dict, List, Tuple, Optional
from pathlib import Path

import numpy as np
import pydicom
from czifile import CziFile, DirectoryEntryDV
from PIL import Image
from pydicom.uid import UID as Uid
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicomizer.encoding import Encoder

from wsidicomizer.imagedata_wrapper import ImageDataWrapper


class CziWrapper(ImageDataWrapper):
    _default_z = 0

    def __init__(
        self,
        filepath: str,
        tile_size: int,
        encoder: Encoder
    ) -> None:
        """Wraps a czi file to ImageData. Multiple z, c, or pyramid levels are
        currently not supported.

        Parameters
        ----------
        filepath: str
            Path to czi file to wrap.
        tile_size: int
            Output tile size.
        jpeg: TurboJPEG
            TurboJPEG object to use.
        jpeg_quality: Literal = 95
            Jpeg encoding quality to use.
        jpeg_subsample: Literal = TJSAMP_444
            Jpeg subsample option to use:
                TJSAMP_444 - no subsampling
                TJSAMP_420 - 2x2 subsampling
        """

        self._czi = CziFile(filepath)
        self._czi._fh.lock = True
        self._samples_per_pixel = self._get_samples_per_pixel()

        self._dtype = self._czi.dtype
        super().__init__(encoder)
        self._tile_size = Size(tile_size, tile_size)
        self._image_size = Size(self._czi.shape[4], self._czi.shape[3])
        self._image_origin = Point(self._czi.start[4], self._czi.start[3])
        self._focal_plane_mapping = self._get_focal_plane_mapping()
        self._channel_mapping = self._get_channel_mapping()
        self._block_directory = self._czi.filtered_subblock_directory
        self._tile_directory = self._create_tile_directory()
        self._blank_decoded_tile = Image.fromarray(self._create_blank_tile())
        self._blank_encoded_tile = self._encode(self._create_blank_tile())
        self._pixel_spacing = self._get_pixel_spacing()
        self._focal_planes = sorted(self._focal_plane_mapping)

    @property
    def pyramid_index(self) -> int:
        return 0

    @property
    def transfer_syntax(self) -> Uid:
        return self._encoder.transfer_syntax

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
    def focal_planes(self) -> List[float]:
        """Focal planes avaiable in the image defined in um."""
        return self._focal_planes

    @property
    def optical_paths(self) -> List[str]:
        """Optical paths avaiable in the image."""
        return self._channel_mapping

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
    def tile_directory(self) -> Dict[Tuple[Point, float, str], List[int]]:
        """Return dict of tiles with mosaic indices."""
        return self._tile_directory

    @property
    def samples_per_pixel(self) -> int:
        return self._samples_per_pixel

    @staticmethod
    def detect_format(filepath: Path) -> Optional[str]:
        try:
            czi = CziFile(filepath)
            czi.close()
            return 'czi'
        except ValueError:
            return None

    def _get_scaling(
        self
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        metadata = ET.fromstring(self._czi.metadata()).find('Metadata')
        scaling = metadata.find('Scaling')
        scaling_elements = scaling.find('Items')
        x: float = None
        y: float = None
        z: float = None
        for distance in scaling_elements.findall('Distance'):
            dimension = distance.get('Id')
            # Value is in m per pixel, result in mm per pixel
            value = float(distance.find('Value').text) * pow(10, 6)
            if dimension == 'X':
                x = value
            elif dimension == 'Y':
                y = value
            elif dimension == 'Z':
                z = value
        return x, y, z

    def _get_pixel_spacing(self) -> SizeMm:
        """Get pixel spacing (mm per pixel) from metadata"""
        x, y, _ = self._get_scaling()
        if x is None or y is None:
            raise ValueError("Could not find pixel spacing in metadata")
        return SizeMm(x, y)/1000

    def _create_blank_tile(self, fill: float = 1) -> np.ndarray:
        """Return blank tile in numpy array.

        Parameters
        ----------
        fill: float = 1
            Value to fill tile with.

        Returns
        ----------
        np.ndarray
            A blank tile as numpy array.
        """
        return np.full(
            self._size_to_numpy_shape(self.tile_size),
            fill * np.iinfo(self._czi.dtype).max,
            dtype=self._czi.dtype
        )

    def _get_tile(
        self,
        tile_point: Point,
        z: float,
        path: str
    ) -> np.ndarray:
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

        for block_index in self.tile_directory[tile_point, z, path]:
            # For each block covering the tile
            block = self._block_directory[block_index]
            block_data: np.ndarray = block.data_segment().data()

            # Start and end coordiantes for block and tile
            block_start, block_size = self._get_block_start_and_size(block)
            block_end = block_start + block_size
            tile_start = tile_point * self.tile_size
            tile_end = (tile_point + 1) * self.tile_size

            # The block and tile both cover the region between these points
            tile_block_min_intersection = Point.max(tile_start, block_start)
            tile_block_max_intersection = Point.min(tile_end, block_end)

            # The intersects in relation to block and tile origin
            block_start_in_tile = tile_block_min_intersection - tile_start
            block_end_in_tile = tile_block_max_intersection - tile_start
            tile_start_in_block = tile_block_min_intersection - block_start
            tile_end_in_block = tile_block_max_intersection - block_start

            # Reshape the block data to remove leading 1-indices.
            block_data.shape = self._size_to_numpy_shape(block_size)
            # Paste in block data into tile.
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
        Image.Image
            Tile as Image.
        """
        if (tile, z, path) not in self.tile_directory:
            return self.blank_decoded_tile
        return Image.fromarray(self._get_tile(tile, z, path))

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return image bytes for tile. Tole is encoded as jpeg.

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
        if self._dtype != np.uint8:
            frame = (frame * 255 / np.iinfo(self._dtype)).astype(np.uint8)
        return self._encode(self._get_tile(tile, z, path))

    def close(self) -> None:
        """Close wrapped file."""
        self._czi.close()

    def _create_tile_directory(
        self
    ) -> Dict[Tuple[Point, float, str], List[int]]:
        """Create a directory mapping tile points to list of block indices that
        cover the tile. This could be extended to also index z and c.

        Returns
        ----------
        Dict[Tuple[Point, int, int], List[int]]:
            Directory of tile point, focal plane and channel as key and
            lists of block indices as item.
        """
        tile_directory: DefaultDict[Tuple[Point, float, str], List[int]] = (
            defaultdict(list)
        )

        for block_index, block in enumerate(self.block_directory):
            block_start, block_size, z, c = self._get_block_dimensions(block)
            tile_region = Region.from_points(
                block_start // self.tile_size,
                (block_start+block_size) // self.tile_size
            )
            for tile in tile_region.iterate_all(include_end=True):
                tile_directory[tile, z, c].append(block_index)

        return dict(tile_directory)

    def _get_block_start_and_size(
        self,
        block: DirectoryEntryDV
    ) -> Tuple[Point, Size]:
        """Return start coordinate and size for block realtive to image
        origin.

        Parameters
        ----------
        block: DirectoryEntryDV
            Block to get start and size from.

        Returns
        ----------
        Tuple[Point, Size]
            Start point corrdinate and size for block.
        """
        x_start: int = None
        x_size: int = None
        y_start: int = None
        y_size: int = None

        for dimension_entry in block.dimension_entries:
            if dimension_entry.dimension == 'X':
                x_start = dimension_entry.start
                x_size = dimension_entry.size
            elif dimension_entry.dimension == 'Y':
                y_start = dimension_entry.start
                y_size = dimension_entry.size
        if None in [x_start, x_size, y_start, y_size]:
            raise ValueError(
                "Could not determine position of block"
            )

        return (
            Point(x_start, y_start) - self.image_origin,
            Size(x_size, y_size)
        )

    def _get_block_dimensions(
        self,
        block: DirectoryEntryDV
    ) -> Tuple[Point, Size, float, str]:
        """Return start coordinate and size for block realtive to image
        origin. This could be extended to also get z and c.

        Parameters
        ----------
        block: DirectoryEntryDV
            Block to get start and size from.

        Returns
        ----------
        Tuple[Point, Size]
            Start point corrdinate and size for block.
        """
        start, size = self._get_block_start_and_size(block)
        z = 0.0
        c = '0'
        for dimension_entry in block.dimension_entries:
            if dimension_entry.dimension == 'X':
                x_start = dimension_entry.start
                x_size = dimension_entry.size
            elif dimension_entry.dimension == 'Y':
                y_start = dimension_entry.start
                y_size = dimension_entry.size
            elif dimension_entry.dimension == 'Z':
                z = self._focal_plane_mapping[dimension_entry.start]
            elif dimension_entry.dimension == 'C':
                c = self._channel_mapping[dimension_entry.start]
        if None in [x_start, x_size, y_start, y_size]:
            raise ValueError(
                "Could not determine position of block"
            )

        return start, size, z, c

    def _size_to_numpy_shape(self, size: Size) -> Tuple[int, int, int]:
        """Return a tuple for use with numpy.shape."""
        return size.height, size.width, self.samples_per_pixel

    def _get_focal_plane_mapping(self) -> List[float]:
        metadata = ET.fromstring(self._czi.metadata()).find('Metadata')
        information = metadata.find('Information')
        image = information.find('Image')
        try:
            size_z = int(image.find('SizeZ').text)
            dimensions = image.find('Dimensions')
            z_dimension = dimensions.find('Z')
            z_positions = z_dimension.find('Positions')
            z_interval = z_positions.find('Interval')
            start = int(z_interval.find('Start').text)
            increment = int(z_interval.find('Increment').text)
            _, _, z_scale = self._get_scaling()
            return range(
                start*z_scale,
                (start+increment*size_z)*z_scale,
                increment*z_scale
            )
        except AttributeError:
            return [0.0]

    def _get_channel_mapping(self) -> List[str]:
        metadata = ET.fromstring(self._czi.metadata()).find('Metadata')
        information = metadata.find('Information')
        image = information.find('Image')
        dimensions = image.find('Dimensions')
        channels = dimensions.find('Channels')
        return [channel.find('Fluor').text for channel in channels]

    def _get_samples_per_pixel(self) -> int:
        return self._czi.shape[-1]
