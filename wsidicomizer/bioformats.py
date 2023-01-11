import os
from contextlib import contextmanager
from functools import cached_property, lru_cache
from pathlib import Path
from queue import Empty, SimpleQueue
from tempfile import TemporaryDirectory
from threading import Lock
from typing import (ContextManager, Dict, Generator, List, Optional, Sequence,
                    Tuple, Type, Union)

import numpy as np
import ome_types
import scyjava
from jpype.types import JArray
from PIL import Image
from pydicom import Dataset
from pydicom.uid import UID
from wsidicom import (WsiDicom, WsiDicomLabels, WsiDicomLevels,
                      WsiDicomOverviews, WsiInstance)
from wsidicom.geometry import Point, Region, Size, SizeMm

from wsidicomizer.common import MetaDicomizer, MetaImageData
from wsidicomizer.dataset import create_base_dataset
from wsidicomizer.encoding import Encoder, create_encoder

"""
Set version of bioformats jar to use with the environmental variable
"BIOFORMATS_VERSION". Note the bioformats jar either has a BSD or GPL-2
license.
"""
bioformats_version = os.getenv('BIOFORMATS_VERSION', 'bsd:6.11.0')
scyjava.config.endpoints.append(f'ome:formats-{bioformats_version}')

if not scyjava.jvm_started():
    scyjava.start_jvm()

"""
Load bioformats modules using jpype and scyjava
"""

from loci.common.services import ServiceFactory  # type: ignore # noqa
from loci.formats import ImageReader, Memoizer  # type: ignore # noqa
from loci.formats.services import OMEXMLService  # type: ignore # noqa


class ReaderPool:
    def __init__(
        self,
        filepath: Path,
        max_readers: Optional[int] = None,
        cache_path: Optional[Union[Path, str]] = None
    ):
        self._filepath = filepath
        if max_readers is None:
            cpu_count = os.cpu_count()
            if cpu_count is not None:
                max_readers = cpu_count
            else:
                max_readers = 1
        self._max_readers = max_readers
        self._current_count = 0
        if cache_path is None:
            self._tempdir = TemporaryDirectory()
            self._cache_path = Path(self._tempdir.name)
        else:
            self._tempdir = None
            self._cache_path = Path(cache_path)
        self._queue = SimpleQueue()
        self._lock = Lock()

    @property
    def filepath(self) -> Path:
        return self._filepath

    @contextmanager
    def get_reader(self) -> Generator[Memoizer, None, None]:
        """Return a reader. Should be used as a context manager. Will block
        if no reader is avaiable."""
        reader = self._get_reader()
        try:
            yield reader
        finally:
            self._return_reader(reader)

    @property
    def _is_full(self) -> bool:
        return self._current_count == self._max_readers

    @property
    def _is_empty(self) -> bool:
        return self._current_count == 0

    def _increment(self):
        if self._current_count < self._max_readers:
            self._current_count += 1
            return
        raise ValueError()

    def _decrement(self):
        if self._current_count > 0:
            self._current_count -= 1
            return
        raise ValueError()

    def _get_reader(self) -> Memoizer:
        """Return a reader with no wait if one is avaiable. Else if current
        reader count is less than maximum reader count return a new reader.
        Otherwise wait for an avaiable readern."""
        try:
            return self._queue.get_nowait()
        except Empty:
            pass
        with self._lock:
            if not self._is_full:
                self._increment()
                return self._create_new_reader()

        return self._queue.get(block=True, timeout=None)

    def _create_new_reader(self) -> Memoizer:
        """Return a new reader."""
        # Create a reader using Memoizer to load file faster
        # See https://docs.openmicroscopy.org/bio-formats/6.11.0/developers/matlab-dev.html#reader-performance  # NOQA
        reader = Memoizer(
            ImageReader(),
            0,
            self._cache_path
        )
        reader.setFlattenedResolutions(False)
        reader.setId(str(self._filepath))
        return reader

    def _return_reader(self, reader: Memoizer) -> None:
        """Release a used reader."""
        self._queue.put(reader)

    def close(self) -> None:
        """Close all readers and clean up cache directory if a temporary
        directory.
        """
        with self._lock:
            while not self._is_empty:
                reader = self._queue.get()
                reader.close()
                self._decrement()
            if self._tempdir is not None:
                self._tempdir.cleanup()


class BioFormatsReader:
    def __init__(
        self,
        filepath: Path,
        max_readers: Optional[int] = None,
        cache_path: Optional[Union[Path, str]] = None
    ):
        """Reader for image data and metadata from file using Bio-Formats api.

        Parameters
        ----------
        filepath: Path
            Path to file to open.
        max_readers: int
            Maximum number of readers to use. If not specified the number
            of cpus will be used.
        cache_path: Optional[Union[Path, str]] = None
            Path to store cache file quicker opening of new readers. If None
            a temporary directory will be used.
        """
        self._reader_pool = ReaderPool(filepath, max_readers, cache_path)

        with self._reader_pool.get_reader() as reader:
            for image in range(reader.getSeriesCount()):
                reader.setSeries(image)
                order = reader.getDimensionOrder()
                rgb_channel_count = reader.getRGBChannelCount()
                interleaved = reader.isInterleaved()
                indexed = reader.isIndexed()
                width = reader.getSizeX()
                rgb = reader.isRGB()
                height = reader.getSizeY()
                level = reader.getResolution()
                pixels = self.metadata.images[image].pixels
                name = self.metadata.images[image].name
                resolutions = reader.getResolutionCount()
                print(
                    image, name, order, rgb_channel_count, indexed,
                    interleaved, rgb, (width, height), pixels.physical_size_x,
                    level, resolutions
                )

            self._resolution_counts = [
                self._get_resolution_count(reader, image_index)
                for image_index in range(self.images_count)
            ]

            self._resolution_scales = {
                image_index: self._get_resolution_scales(
                    reader,
                    image_index
                )
                for image_index in range(self.images_count)
            }

    @staticmethod
    def _get_resolution_count(reader: Memoizer, image_index: int) -> int:
        reader.setSeries(image_index)
        return reader.getResolutionCount()

    @staticmethod
    def _get_resolution_scale(
        reader: Memoizer,
        resolution_index: int,
        base_width: int
    ):
        reader.setResolution(resolution_index)
        width = reader.getSizeX()
        return int(round(base_width/width))

    @classmethod
    def _get_resolution_scales(
        cls,
        reader: Memoizer,
        image_index: int
    ) -> List[int]:
        reader.setSeries(image_index)
        reader.setResolution(0)
        base_width = reader.getSizeX()
        return [
            cls._get_resolution_scale(reader, resolution_index, base_width)
            for resolution_index in range(reader.getResolutionCount())
        ]

    @property
    def filepath(self) -> Path:
        """Return filepath of the opened file."""
        return self._reader_pool.filepath

    @cached_property
    def metadata(self) -> ome_types.OME:
        """Return parsed metadata."""
        metadata = self._read_metadata()
        return ome_types.from_xml(str(metadata), parser='lxml')

    @property
    def images_count(self) -> int:
        return len(self.metadata.images)

    def resolution_count(self, image_index: int) -> int:
        return self._resolution_counts[image_index]

    def image_name(self, image_index: int) -> Optional[str]:
        return self.metadata.images[image_index].name

    @lru_cache
    def dtype(self, image_index: int) -> np.dtype:
        """Return the numpy datatype for image in file."""
        NUMPY_DATA_TYPES: Dict[str, Type] = {
            'bit': np.bool_,
            'double-complex': np.cdouble,
            'complex': np.csingle,
            'double': np.float64,
            'float':  np.float32,
            'int16': np.int16,
            'int32': np.int32,
            'int8': np.int8,
            'uint16': np.uint16,
            'uint32': np.uint32,
            'uint8': np.uint8
        }
        if self.metadata.images[image_index].pixels.big_endian:
            byte_order = '>'
        else:
            byte_order = '<'
        data_type = self.metadata.images[image_index].pixels.type.value
        try:
            numpy_data_type = np.dtype(NUMPY_DATA_TYPES[data_type])
        except KeyError:
            raise ValueError(f'Unkown data type {data_type}')
        return numpy_data_type.newbyteorder(byte_order)

    @lru_cache
    def samples_per_pixel(self, image_index: int) -> int:
        """Return the samples per pixel for image in file."""
        pixels = self.metadata.images[image_index].pixels
        samples_per_pixel = pixels.channels[0].samples_per_pixel
        assert samples_per_pixel is not None
        return int(samples_per_pixel)

    @lru_cache
    def size(self, image_index: int, resolution_index: int = 0) -> Size:
        """Return the image size for image in file."""
        pixels = self.metadata.images[image_index].pixels
        scale = self._resolution_scales[image_index][resolution_index]
        return Size(int(pixels.size_x), int(pixels.size_y)) // scale

    @lru_cache
    def pixel_spacing(
        self,
        image_index: int,
        resolution_index: int = 0
    ) -> Optional[SizeMm]:
        """Return the size of the pixels in mm/pixel for image in file."""
        pixels = self.metadata.images[image_index].pixels
        if (
            pixels.physical_size_x is None
            or pixels.physical_size_y is None
        ):
            return None
        scale = self._resolution_scales[image_index][resolution_index]
        print(image_index, resolution_index, scale)
        return SizeMm(
            float(pixels.physical_size_x),
            float(pixels.physical_size_y)
        ) * scale / 1000

    @lru_cache
    def is_interleaved(self, image_index: int) -> bool:
        interleaved = self.metadata.images[image_index].pixels.interleaved
        assert interleaved is not None
        return interleaved

    @contextmanager
    def read_image(
        self,
        image_index: int,
        resolution_index: int,
        region: Region,
        index: int = 0,
    ) -> Generator[np.ndarray, None, None]:
        """Read image data from file. Preferably used as a context manager.
        Data is returned as a memoryview that should be released after use.

        Parameters
        ----------
        image_index: int
            The image to read data from.
        region: Region
            The region to read data from.
        index: int
            The index in image to read data from.

        Returns
        ----------
            Generator[np.ndarray, None, None]

        """
        raw_data = memoryview(
            self._read(
                image_index,
                resolution_index,
                index,
                region.start.x,
                region.start.y,
                region.size.width,
                region.size.height
            )
        )
        try:
            data = np.frombuffer(raw_data, self.dtype(image_index))
            if self.is_interleaved(image_index):
                yield data.reshape(
                    region.size.height,
                    region.size.width,
                    self.samples_per_pixel(image_index)
                )
            else:
                data = data.reshape(
                    self.samples_per_pixel(image_index),
                    region.size.height,
                    region.size.width
                )
                data = np.moveaxis(data, 0, 2)
                yield data.copy()
        finally:
            raw_data.release()

    def close(self) -> None:
        """Close all readers and clean up cache directory if a temporary
        directory.
        """
        self._reader_pool.close()

    def _read(
        self,
        image_index: int,
        resolution_index: int,
        index: int,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int
    ) -> JArray:
        """Read image data from file.
        """
        with self._reader_pool.get_reader() as reader:
            reader.setSeries(image_index)
            reader.setResolution(resolution_index)
            return reader.openBytes(
                index,
                start_x,
                start_y,
                end_x,
                end_y
            )

    def _read_metadata(self) -> str:
        """Read metadata from file."""
        service_factory = ServiceFactory()
        metadata_service = service_factory.getInstance(OMEXMLService)
        metadata_store = metadata_service.createOMEXMLMetadata()

        with self._reader_pool.get_reader() as reader:
            reader.close()
            reader.setFlattenedResolutions(False)
            reader.setOriginalMetadataPopulated(True)
            reader.setMetadataStore(metadata_store)
            reader.setId(str(self._reader_pool.filepath))
            metadata = str(metadata_store.dumpXML())

        return metadata


class BioFormatsImageData(MetaImageData):
    def __init__(
        self,
        reader: BioFormatsReader,
        tile_size: int,
        encoder: Encoder,
        image_index: int,
        resolution_index: int
    ) -> None:
        super().__init__(encoder)
        self._tile_size = Size(tile_size, tile_size)
        self._image_reader = reader
        self._image_index = image_index
        self._resolution_index = resolution_index
        self._image_region = Region(Point(0, 0), self.image_size)

    @property
    def image_region(self) -> Region:
        return self._image_region

    @property
    def pyramid_index(self) -> int:
        """Return pyramid level for image data."""
        return 0

    @property
    def files(self) -> List[Path]:
        return [Path(self._image_reader.filepath)]

    @property
    def transfer_syntax(self) -> UID:
        """Return the uid of the transfer syntax of the image."""
        return self._encoder.transfer_syntax

    @property
    def image_size(self) -> Size:
        """Return the pixel size of the image."""
        return self._image_reader.size(
            self._image_index,
            self._resolution_index
        )

    @property
    def tile_size(self) -> Size:
        """Return the pixel tile size of the image, or pixel size of
        the image if not tiled."""
        return self._tile_size

    @property
    def pixel_spacing(self) -> Optional[SizeMm]:
        """Return the size of the pixels in mm/pixel."""
        return self._image_reader.pixel_spacing(
            self._image_index,
            self._resolution_index
        )

    @property
    def samples_per_pixel(self) -> int:
        """Return number of samples per pixel (e.g. 3 for RGB)."""
        return self._image_reader.samples_per_pixel(self._image_index)

    @property
    def photometric_interpretation(self) -> str:
        """Return the photophotometric interpretation of the image
        data."""
        return self._encoder.photometric_interpretation(self.samples_per_pixel)

    def _get_tile(
        self,
        tile_point: Point,
        z: float,
        path: str
    ) -> ContextManager[np.ndarray]:
        # TODO if cropping region the returned image should still be same size
        region = Region(tile_point*self.tile_size, self.tile_size)
        cropped_region = self.image_region.crop(region)
        return self._image_reader.read_image(
            self._image_index,
            self._resolution_index,
            cropped_region
        )

    def _get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
        """Return Image for tile defined by tile (x, y), z,
        and optical path."""
        with self._get_tile(tile, z, path) as data:
            return Image.fromarray(data)

    def _get_encoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        """Return image bytes for tile defined by tile (x, y), z,
        and optical path."""
        with self._get_tile(tile, z, path) as data:
            return self._encode(data)

    def close(self) -> None:
        """Close any open files."""
        self._image_reader.close()

    @staticmethod
    def detect_format(filepath: str) -> bool:
        try:
            reader = ImageReader(filepath)
            reader.close()
        except Exception:
            return False
        return True


class BioFormatsDicomizer(MetaDicomizer):
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
        jpeg_subsampling: str = '420',
        readers: Optional[int] = None,
        cache_path: Optional[str] = None
    ) -> WsiDicom:
        if tile_size is None:
            raise ValueError("Tile size required for bioformats")
        encoder = create_encoder(
            encoding_format,
            encoding_quality,
            jpeg_subsampling
        )
        base_dataset = create_base_dataset(modules)
        reader = BioFormatsReader(
            Path(filepath),
            readers,
            cache_path
        )
        level_instances, label_instances, overview_instances = (
            cls._create_instances(
                reader,
                tile_size,
                encoder,
                base_dataset,
                include_levels,
                include_label,
                include_overview
            )
        )
        levels = WsiDicomLevels.open(level_instances)
        labels = WsiDicomLabels.open(label_instances)
        overviews = WsiDicomOverviews.open(overview_instances)
        return cls(levels, labels, overviews)

    @staticmethod
    def is_supported(filepath: str) -> bool:
        """Return True if file in filepath is supported by Bio-Formats."""
        return BioFormatsImageData.detect_format(filepath)

    @staticmethod
    def _get_image_indices(
        reader: BioFormatsReader
    ) -> Tuple[int, Optional[int], Optional[int]]:
        image_indices = list(range(reader.images_count))
        overview_image_index = None
        label_image_index = None

        for image_index in image_indices.copy():
            image_name = reader.image_name(image_index)
            if image_name is None:
                continue
            if (
                'macro' in image_name.lower()
                or 'overview' in image_name.lower()
            ):
                overview_image_index = image_index
                image_indices.remove(image_index)
            elif 'label' in image_name.lower():
                label_image_index = image_index
                image_indices.remove(image_index)

        pyramid_image_index = 0
        largest_image_width = None
        for image_index in image_indices:
            image_width = reader.size(image_index).width
            if (
                largest_image_width is None
                or largest_image_width < image_width
            ):
                pyramid_image_index = image_index
                largest_image_width = image_width
        return pyramid_image_index, label_image_index, overview_image_index

    @classmethod
    def _create_instances(
        cls,
        reader: BioFormatsReader,
        tile_size: int,
        encoder: Encoder,
        base_dataset: Dataset,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
    ) -> Tuple[List[WsiInstance], List[WsiInstance], List[WsiInstance]]:
        pyramid_image_index, label_image_index, overview_image_index = (
            cls._get_image_indices(reader)
        )

        level_instances = [
            cls._create_instance(
                BioFormatsImageData(
                    reader,
                    tile_size,
                    encoder,
                    pyramid_image_index,
                    resolution_index
                ),
                base_dataset,
                'VOLUME',
                instance_number
            )
            for instance_number, resolution_index
            in enumerate(range(reader.resolution_count(pyramid_image_index)))
            if include_levels is None or resolution_index in include_levels
        ]
        instance_count = len(level_instances)

        if include_label and label_image_index is not None:
            instance = cls._create_instance(
                BioFormatsImageData(
                    reader,
                    tile_size,
                    encoder,
                    label_image_index,
                    0
                ),
                base_dataset,
                'LABEL',
                instance_count
            )
            instance_count += 1
            label_instances = [instance]
        else:
            label_instances = []

        if include_overview and overview_image_index is not None:
            instance = cls._create_instance(
                BioFormatsImageData(
                    reader,
                    tile_size,
                    encoder,
                    overview_image_index,
                    0
                ),
                base_dataset,
                'OVERVIEW',
                instance_count
            )
            instance_count += 1
            overview_instances = [instance]
        else:
            overview_instances = []

        return level_instances, label_instances, overview_instances
