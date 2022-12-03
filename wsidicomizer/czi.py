#    Copyright 2021 SECTRA AB
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

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property, lru_cache
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Sequence, Tuple, Type, TypeVar, Union
from xml.etree import ElementTree

from dateutil import parser as dateparser
import numpy as np
from czifile import CziFile, DirectoryEntryDV
from opentile.metadata import Metadata
from PIL import Image
from pydicom import Dataset
from pydicom.uid import UID as Uid
from wsidicom import (WsiDicom, WsiDicomLabels, WsiDicomLevels,
                      WsiDicomOverviews)
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.wsidicom import WsiDicom

from wsidicomizer.common import MetaDicomizer, MetaImageData
from wsidicomizer.config import settings
from wsidicomizer.dataset import create_base_dataset
from wsidicomizer.encoding import Encoder, create_encoder

ElementType = TypeVar('ElementType', str, int, float)


class CziMetadata(Metadata):
    def __init__(
        self,
        czi: CziFile
    ):
        metadata_xml = czi.metadata()
        if metadata_xml is None or not isinstance(metadata_xml, str):
            raise ValueError("No metadata string in file.")
        self._metadata = ElementTree.fromstring(metadata_xml)

    @property
    def aquisition_datetime(self) -> Optional[datetime]:
        value = self.get_value_from_element(
            self._metadata,
            'AcquisitionDateAndTime',
            str,
            nested=['Metadata', 'Information', 'Image']
        )
        return dateparser.parse(value)

    @property
    def scanner_model(self) -> Optional[str]:
        information = self.get_nested_element(['Metadata', 'Information'])
        image = self.get_nested_element(['Image'], information)
        microscope_ref = self.get_element(image, 'MicroscopeRef').get('Id')
        microscopes = self.get_nested_element(
            ['Instrument', 'Microscopes'],
            information
        ).findall('Microscope')
        try:
            microscope = next(
                microscope for microscope in microscopes
                if microscope.get('Id') == microscope_ref
            )
        except StopIteration:
            return None
        return microscope.get('Name')

    @property
    def magnification(self) -> Optional[float]:
        information = self.get_nested_element(['Metadata', 'Information'])
        objective_refs = [
            objective.get('Id') for objective in
            self.get_nested_element(
                ['Image', 'ObjectiveSettings'],
                information
            ).findall('ObjectiveRef')
        ]
        if len(objective_refs) != 1:
            return None
        objectives = self.get_nested_element(
            ['Instrument', 'Objectives'],
            information
        ).findall('Objective')
        try:
            objective = next(
                objective for objective in objectives
                if objective.get('Id') == objective_refs[0]
            )
        except StopIteration:
            return None
        try:
            return self.get_value_from_element(
                objective,
                'NominalMagnification',
                float
            )
        except ValueError:
            return None

    @property
    def scanner_software_versions(self) -> Optional[List[str]]:
        application = self.get_nested_element(
            ['Metadata', 'Information', 'Application']
        )
        try:
            name = self.get_value_from_element(application, 'Name', str)
            version = self.get_value_from_element(application, 'Version', str)
        except ValueError:
            return None
        return [name + ' ' + version]

    @cached_property
    def scaling(
        self
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        scaling_elements = self.get_nested_element(
            ['Metadata', 'Scaling', 'Items']
        )
        x: Optional[float] = None
        y: Optional[float] = None
        z: Optional[float] = None
        for distance in scaling_elements.findall('Distance'):
            dimension = distance.get('Id')
            # Value is in m per pixel, result in mm per pixel
            value = self.get_value_from_element(
                distance,
                'Value',
                float,
            ) * pow(10, 6)
            if dimension == 'X':
                x = value
            elif dimension == 'Y':
                y = value
            elif dimension == 'Z':
                z = value
        return x, y, z

    @cached_property
    def pixel_spacing(self) -> SizeMm:
        """Get pixel spacing (mm per pixel) from metadata"""
        x, y, _ = self.scaling
        if x is None or y is None:
            raise ValueError("Could not find pixel spacing in metadata")
        return SizeMm(x, y)/1000

    @cached_property
    def focal_plane_mapping(self) -> List[float]:
        image = self.get_nested_element(
            ["Metadata", 'Information', 'Image']
        )
        try:
            size_z = self.get_value_from_element(image, 'SizeZ', int, 0)
            z_interval = self.get_nested_element(
                ['Dimensions', 'Z', 'Positions', 'Interval'],
                image
            )
            start = self.get_value_from_element(z_interval, 'Start', int)
            increment = self.get_value_from_element(
                z_interval,
                'Increment',
                int
            )
            _, _, z_scale = self.scaling
            if z_scale is None:
                raise ValueError("No z scale in metadata")
            start_z = start * z_scale
            end_z = (start+increment*size_z)*z_scale
            step_z = increment*z_scale
            return list(np.arange(start_z, end_z, step_z))
        except ValueError:
            return [0.0]

    @cached_property
    def channel_mapping(self) -> List[str]:
        channels = self.get_nested_element(
            ['Metadata', 'Information', 'Image', 'Dimensions', 'Channels']
        )
        return [
            self.get_value_from_element(channel, 'Fluor', str)
            for channel in channels
        ]

    def get_nested_element(
        self,
        tags: Sequence[str],
        element: Optional[ElementTree.Element] = None
    ) -> ElementTree.Element:
        if element is None:
            element = self._metadata
        found_element = element
        for tag in tags:
            found_element = found_element.find(tag)
            if found_element is None:
                raise ValueError(f"Tag {tag} not found in element")
        return found_element

    def get_value_from_element(
        self,
        element: ElementTree.Element,
        tag: str,
        value_type: Type[ElementType],
        default: Optional[ElementType] = None,
        nested: Optional[Sequence[str]] = None
    ) -> ElementType:
        if nested is not None:
            element = self.get_nested_element(nested, element)
        try:
            element = self.get_element(element, tag)
            text = element.text
            if text is None:
                raise ValueError("Text not found in element")
        except ValueError as exception:
            if default is not None:
                return default
            raise ValueError(
                f"Tag {tag} or text not found in element"
            ) from exception
        try:
            return value_type(text)
        except ValueError as exception:
            raise ValueError(
                f'Failed to convert tag {tag} value {text} to {value_type}.'
            ) from exception

    @staticmethod
    def get_element(
        element: ElementTree.Element,
        tag: str
    ) -> ElementTree.Element:
        found_element = element.find(tag)
        if found_element is None:
            raise ValueError(f"Tag {tag} not found in element")
        return found_element


@dataclass
class CziBlock:
    index: int
    start: Point
    size: Size


class CziImageData(MetaImageData):
    def __init__(
        self,
        filepath: str,
        tile_size: int,
        encoder: Encoder
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
        """
        self._filepath = filepath
        self._czi = CziFile(filepath)
        self._czi._fh.lock = True
        self._dtype = self._czi.dtype
        super().__init__(encoder)
        self._tile_size = Size(tile_size, tile_size)
        self._metadata = CziMetadata(self._czi)
        assert isinstance(self._czi.filtered_subblock_directory, list)
        self._block_directory = self._czi.filtered_subblock_directory
        self._block_locks: Dict[int, Lock] = defaultdict(Lock)

    @property
    def pyramid_index(self) -> int:
        return 0

    @property
    def files(self) -> List[Path]:
        return [Path(self._filepath)]

    @property
    def transfer_syntax(self) -> Uid:
        return self._encoder.transfer_syntax

    @cached_property
    def photometric_interpretation(self) -> str:
        return self._encoder.photometric_interpretation(self.samples_per_pixel)

    @property
    def pixel_spacing(self) -> SizeMm:
        return self._metadata.pixel_spacing

    @cached_property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return Size(
            self._get_size(axis='X'),
            self._get_size(axis='Y')
        )

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @cached_property
    def tiled_size(self) -> Size:
        return self.image_size.ceil_div(self.tile_size)

    @cached_property
    def focal_planes(self) -> List[float]:
        """Focal planes avaiable in the image defined in um."""
        return sorted(self._metadata.focal_plane_mapping)

    @property
    def optical_paths(self) -> List[str]:
        """Optical paths avaiable in the image."""
        return self._metadata.channel_mapping

    @cached_property
    def blank_decoded_tile(self) -> Image.Image:
        return Image.fromarray(self._create_blank_tile())

    @cached_property
    def blank_encoded_tile(self) -> bytes:
        return self._encode(self._create_blank_tile())

    @cached_property
    def image_origin(self) -> Point:
        """Return coordinate of the top-left of the image."""
        return Point(
            self._get_start(axis='X'),
            self._get_start(axis='Y')
        )

    @cached_property
    def tile_directory(
        self
    ) -> Dict[Tuple[Point, float, str], List[CziBlock]]:
        """Return dict of block, block start, and block size by tile position,
        focal plane and optical path

        Returns
        ----------
        Dict[Tuple[Point, float, str], Sequence[CziBlock]]:
            Directory of tile point, focal plane and channel as key and
            list of block, block start, and block size as item.
        """
        tile_directory: Dict[Tuple[Point, float, str], List[CziBlock]] = (
            defaultdict(list)
        )
        assert isinstance(self._czi.filtered_subblock_directory, list)
        for index, block in enumerate(self._czi.filtered_subblock_directory):
            block_start, block_size, z, c = self._get_block_dimensions(block)
            tile_region = Region.from_points(
                block_start // self.tile_size,
                (block_start+block_size) // self.tile_size
            )
            for tile in tile_region.iterate_all(include_end=True):
                tile_directory[tile, z, c].append(
                    CziBlock(index, block_start, block_size)
                )

        return tile_directory

    @property
    def metadata(self) -> CziMetadata:
        return self._metadata

    @cached_property
    def samples_per_pixel(self) -> int:
        return self._get_size(axis='0')

    @property
    def block_directory(self) -> List[DirectoryEntryDV]:
        return self._block_directory

    @staticmethod
    def detect_format(filepath: Path) -> Optional[str]:
        try:
            czi = CziFile(filepath)
            czi.close()
            return 'czi'
        except ValueError:
            return None

    def close(self) -> None:
        """Close wrapped file."""
        self._czi.close()

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
                block_start_in_tile.y:block_end_in_tile.y,
                block_start_in_tile.x:block_end_in_tile.x,
            ] = block_data[
                tile_start_in_block.y:tile_end_in_block.y,
                tile_start_in_block.x:tile_end_in_block.x
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
        return self._encode(frame)

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
            raise ValueError(f'Axis {axis} not found in axes {self._czi.axes}')
        return index

    def _create_blank_tile(self) -> np.ndarray:
        """Return blank tile in numpy array.

        Returns
        ----------
        np.ndarray
            A blank tile as numpy array.
        """
        if self.photometric_interpretation == 'MONOCHROME2':
            fill_value = 0
        else:
            fill_value = 1
        assert isinstance(self._czi.dtype, np.dtype)
        return np.full(
            self._size_to_numpy_shape(self.tile_size),
            fill_value * np.iinfo(self._czi.dtype).max,
            dtype=np.dtype(self._czi.dtype)
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
        self,
        block: DirectoryEntryDV
    ) -> Tuple[Point, Size, float, str]:
        """Return start coordinate and size for block realtive to image
        origin and block focal plane and optical path.

        Parameters
        ----------
        block: DirectoryEntryDV
            Block to get start and size from.

        Returns
        ----------
        Tuple[Point, Size]
            Start point corrdinate, size, focal plane and optical path for
            block.
        """
        x_start: Optional[int] = None
        x_size: Optional[int] = None
        y_start: Optional[int] = None
        y_size: Optional[int] = None
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
                z = self.metadata.focal_plane_mapping[dimension_entry.start]
            elif dimension_entry.dimension == 'C':
                c = self.metadata.channel_mapping[dimension_entry.start]

        if (
            x_start is None or x_size is None or
            y_start is None or y_size is None
        ):
            raise ValueError("Could not determine position of block.")

        return (
            Point(x_start, y_start) - self.image_origin,
            Size(x_size, y_size),
            z,
            c
        )

    def _size_to_numpy_shape(self, size: Size) -> Tuple[int, ...]:
        """Return a tuple for use with numpy.shape."""
        if self.samples_per_pixel == 1:
            return size.height, size.width
        return size.height, size.width, self.samples_per_pixel


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
        jpeg_subsampling: str = '420'
    ) -> WsiDicom:
        """Open czi file in filepath as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to tiff file
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: Optional[int]
            Tile size to use if not defined by file.
        include_levels: Sequence[int] = None
            Levels to include. Not implemented.
        include_label: bool = True
            Inclube label. Not implemented.
        include_overview: bool = True
            Include overview. Not implemented.
        include_confidential: bool = True
            Include confidential metadata. Not implemented.
        encoding_format: str = 'jpeg'
            Encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'.
        encoding_quality: int = 90
            Quality to use if re-encoding. Do not use > 95 for jpeg. Use 100
            for lossless jpeg2000.
        jpeg_subsampling: str = '420'
            Subsampling option if using jpeg for re-encoding. Use '444' for
            no subsampling, '422' for 2x1 subsampling, and '420' for 2x2
            subsampling.

        Returns
        ----------
        WsiDicom
            WsiDicom object of czi file in filepath.
        """
        if tile_size is None:
            raise ValueError("Tile size required for czi")
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
        """Return True if file in filepath is supported by CziFile."""
        return CziImageData.detect_format(Path(filepath)) is not None
