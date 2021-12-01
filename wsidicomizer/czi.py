import xml.etree.ElementTree as ElementTree
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from czifile import CziFile, DirectoryEntryDV
from PIL import Image
from pydicom import Dataset
from pydicom.uid import UID as Uid
from wsidicom import (WsiDicom, WsiDicomLabels, WsiDicomLevels,
                      WsiDicomOverviews)
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.wsidicom import WsiDicom

from wsidicomizer.common import MetaImageData, MetaDicomizer
from wsidicomizer.dataset import create_base_dataset
from wsidicomizer.encoding import Encoder, create_encoder


def get_element(element: ElementTree.Element, tag: str) -> ElementTree.Element:
    found_element = element.find(tag)
    if found_element is None:
        raise ValueError(f"Tag {tag} not found in element")
    return found_element


def get_nested_element(
    element: ElementTree.Element,
    tags: List[str]
) -> ElementTree.Element:
    found_element = element
    for tag in tags:
        found_element = found_element.find(tag)
        if found_element is None:
            raise ValueError(f"Tag {tag} not found in element")
    return found_element


def get_text_from_element(
    element: ElementTree.Element,
    tag: str,
    default: Optional[str] = None
) -> str:
    try:
        element = get_element(element, tag)
        text = element.text
        if text is None:
            raise ValueError("Text not found in element")
    except ValueError:
        if default is not None:
            return default
        raise ValueError(f"Tag {tag} or text not found in element")
    return text


class CziImageData(MetaImageData):
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
        encoded: Encoder
            Encoded to use.
        """
        self._filepath = filepath
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
    def files(self) -> List[Path]:
        return [Path(self._filepath)]

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
    def tile_directory(self) -> Dict[Tuple[Point, float, str], Sequence[int]]:
        """Return dict of tiles with mosaic indices."""
        return self._tile_directory

    @property
    def metadata(self) -> str:
        metadata_xml = self._czi.metadata()
        if metadata_xml is None or not isinstance(metadata_xml, str):
            raise ValueError("No metadata string in file")
        return metadata_xml

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
        scaling_elements = get_nested_element(
            ElementTree.fromstring(self.metadata),
            ['Metadata', 'Scaling', 'Items']
        )
        x: Optional[float] = None
        y: Optional[float] = None
        z: Optional[float] = None
        for distance in scaling_elements.findall('Distance'):
            dimension = distance.get('Id')
            # Value is in m per pixel, result in mm per pixel
            value = (
                float(get_text_from_element(distance, 'Value')) * pow(10, 6)
            )
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
            dtype=np.dtype(self._czi.dtype)
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

    def _get_decoded_tile(
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
        if self._dtype != np.dtype(np.uint8):
            frame = (frame * 255 / np.iinfo(self._dtype)).astype(np.uint8)
        return self._encode(self._get_tile(tile, z, path))

    def close(self) -> None:
        """Close wrapped file."""
        self._czi.close()

    def _create_tile_directory(
        self
    ) -> Dict[Tuple[Point, float, str], Sequence[int]]:
        """Create a directory mapping tile points to list of block indices that
        cover the tile. This could be extended to also index z and c.

        Returns
        ----------
        Dict[Tuple[Point, int, int], Sequence[int]]:
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
        x_start: Optional[int] = None
        x_size: Optional[int] = None
        y_start: Optional[int] = None
        y_size: Optional[int] = None

        for dimension_entry in block.dimension_entries:
            if dimension_entry.dimension == 'X':
                x_start = dimension_entry.start
                x_size = dimension_entry.size
            elif dimension_entry.dimension == 'Y':
                y_start = dimension_entry.start
                y_size = dimension_entry.size
        if (
            x_start is None or x_size is None or
            y_start is None or y_size is None
        ):
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
        if start is None or size is None or z is None or c is None:
            raise ValueError(
                "Could not determine position of block"
            )

        return start, size, z, c

    def _size_to_numpy_shape(self, size: Size) -> Tuple[int, int, int]:
        """Return a tuple for use with numpy.shape."""
        return size.height, size.width, self.samples_per_pixel

    def _get_focal_plane_mapping(self) -> List[float]:
        image = get_nested_element(
            ElementTree.fromstring(self.metadata),
            ["Metadata", 'Information', 'Image']
        )
        try:
            size_z = int(get_text_from_element(image, 'SizeZ', '0'))
            z_interval = get_nested_element(
                image,
                ['Dimensions', 'Z', 'Positions', 'Interval']
            )
            start = int(get_text_from_element(z_interval, 'Start'))
            increment = int(get_text_from_element(z_interval, 'Increment'))
            _, _, z_scale = self._get_scaling()
            if z_scale is None:
                raise ValueError("No z scale in metadata")
            start_z = start * z_scale
            step_z = (start+increment*size_z)*z_scale
            end_z = increment*z_scale
            return list(np.arange(start_z, end_z, step_z))
        except ValueError:
            return [0.0]

    def _get_channel_mapping(self) -> List[str]:
        channels = get_nested_element(
            ElementTree.fromstring(self.metadata),
            ['Metadata', 'Information', 'Image', 'Dimensions', 'Channels']
        )
        return [
            get_text_from_element(channel, 'Fluor')
            for channel in channels
        ]

    def _get_samples_per_pixel(self) -> int:
        return self._czi.shape[-1]


class CziDicomizer(MetaDicomizer):
    @classmethod
    def open(
        cls,
        filepath: str,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        tile_size: Optional[int] = None,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '422'
    ) -> WsiDicom:
        """Open data in czi file as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to czi file.
        tile_size: int
            Tile size to use.
        datasets: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Base dataset to use in files. If none, use test dataset.
        encoding_format: str = 'jpeg'
            Encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'.
        encoding_quality: int = 90
            Quality to use if re-encoding. Do not use > 95 for jpeg. Use 100
            for lossless jpeg2000.
        jpeg_subsampling: str = '422'
            Subsampling option if using jpeg for re-encoding. Use '444' for
            no subsampling, '422' for 2x2 subsampling.

        Returns
        ----------
        WsiDicomizer
            WsiDicomizer object of imported czi file.
        """
        if tile_size is None:
            raise ValueError("Tile size required for open slide")
        encoder = create_encoder(
            encoding_format,
            encoding_quality,
            jpeg_subsampling
        )
        base_dataset = create_base_dataset(modules)
        base_level_instance = cls._create_instance(
            CziImageData(filepath, tile_size, encoder),
            base_dataset,
            'VOLUME',
            0
        )
        levels = WsiDicomLevels.open([base_level_instance])
        labels = WsiDicomLabels.open([])
        overviews = WsiDicomOverviews.open([])
        return cls(levels, labels, overviews)

    @staticmethod
    def is_supported(filepath: str) -> bool:
        return CziImageData.detect_format(Path(filepath)) is not None
