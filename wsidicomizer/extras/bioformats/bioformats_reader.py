#    Copyright 2023 SECTRA AB
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

"""Reader for bioformat supported files."""

import os
from contextlib import contextmanager
from functools import cached_property, lru_cache
from pathlib import Path
from queue import Empty, SimpleQueue
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Dict, Generator, List, Optional, Type, Union

import jpype.imports  # Needed for loci import to work # noqa
import numpy as np
import ome_types
import scyjava
from jpype.types import JArray
from wsidicom.geometry import Region, Size, SizeMm

"""
Set version of bioformats jar to use with the environmental variable
"BIOFORMATS_VERSION". Note the bioformats jar either has a BSD or GPL-2
license.
"""
bioformats_version = os.getenv("BIOFORMATS_VERSION", "bsd:6.12.0")
scyjava.config.endpoints.append(f"ome:formats-{bioformats_version}")

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
        cache_path: Optional[Union[Path, str]] = None,
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
        self._queue: SimpleQueue[Memoizer] = SimpleQueue()
        self._lock = Lock()

    @property
    def filepath(self) -> Path:
        return self._filepath

    @contextmanager
    def get_reader(self) -> Generator[Memoizer, None, None]:
        """Return a reader. Should be used as a context manager. Will block
        if no reader is available."""
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
        """Return a reader with no wait if one is available. Else if current
        reader count is less than maximum reader count return a new reader.
        Otherwise wait for an available readern."""
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
        # See https://docs.openmicroscopy.org/bio-formats/6.11.0/developers/matlab-dev.html#reader-performance
        reader = Memoizer(ImageReader(), 0, self._cache_path)
        reader.setFlattenedResolutions(False)
        reader.setId(str(self._filepath))
        return reader

    def _return_reader(self, reader: Memoizer) -> None:
        """Release a used reader."""
        self._queue.put(reader)

    def close(self) -> None:
        """Close all readers and clean up cache directory if a temporary directory."""
        with self._lock:
            while not self._is_empty:
                reader = self._queue.get()
                reader.close()
                self._decrement()
            if self._tempdir is not None:
                self._tempdir.cleanup()


class BioformatsReader:
    def __init__(
        self,
        filepath: Path,
        max_readers: Optional[int] = None,
        cache_path: Optional[Union[Path, str]] = None,
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
            # self.print_debug(reader)
            self._resolution_counts = [
                self._get_resolution_count(reader, image_index)
                for image_index in range(self.images_count)
            ]

            self._resolution_scales = {
                image_index: self._get_resolution_scales(reader, image_index)
                for image_index in range(self.images_count)
            }

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        try:
            reader = ImageReader()
            reader.setId(str(filepath))
            reader.close()
        except Exception:
            return False
        return True

    @staticmethod
    def _get_resolution_count(reader: Memoizer, image_index: int) -> int:
        reader.setSeries(image_index)
        return reader.getResolutionCount()

    @staticmethod
    def _get_resolution_scale(reader: Memoizer, resolution_index: int, base_width: int):
        reader.setResolution(resolution_index)
        width = reader.getSizeX()
        return int(round(base_width / width))

    @classmethod
    def _get_resolution_scales(cls, reader: Memoizer, image_index: int) -> List[int]:
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
        return ome_types.from_xml(str(metadata), parser="lxml")

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
            "bit": np.bool_,
            "double-complex": np.cdouble,
            "complex": np.csingle,
            "double": np.float64,
            "float": np.float32,
            "int16": np.int16,
            "int32": np.int32,
            "int8": np.int8,
            "uint16": np.uint16,
            "uint32": np.uint32,
            "uint8": np.uint8,
        }
        if self.metadata.images[image_index].pixels.big_endian:
            byte_order = ">"
        else:
            byte_order = "<"
        data_type = self.metadata.images[image_index].pixels.type.value
        try:
            numpy_data_type = np.dtype(NUMPY_DATA_TYPES[data_type])
        except KeyError:
            raise ValueError(f"Unkown data type {data_type}")
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
        self, image_index: int, resolution_index: int = 0
    ) -> Optional[SizeMm]:
        """Return the size of the pixels in mm/pixel for image in file."""
        pixels = self.metadata.images[image_index].pixels
        if pixels.physical_size_x is None or pixels.physical_size_y is None:
            return None
        scale = self._resolution_scales[image_index][resolution_index]
        return (
            SizeMm(float(pixels.physical_size_x), float(pixels.physical_size_y))
            * scale
            / 1000
        )

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
        output_size: Optional[Size] = None,
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
        output_size: Optional[Size] = None
            Optional size to resize image data to. Must be equal to or larger than
            region size.
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
                region.size.height,
            )
        )
        try:
            data: np.ndarray = np.frombuffer(raw_data, self.dtype(image_index))
            if self.is_interleaved(image_index):
                data = data.reshape(
                    region.size.height,
                    region.size.width,
                    self.samples_per_pixel(image_index),
                )
            else:
                data = data.reshape(
                    self.samples_per_pixel(image_index),
                    region.size.height,
                    region.size.width,
                )
                data = np.moveaxis(data, 0, 2).copy()
            if output_size is not None and data.shape[0:2] != output_size.to_tuple():
                # Pad with zeros to get requsted output size.
                if not output_size.all_greater_than_or_equal(region.size):
                    raise ValueError(
                        "Output size should be equal to or larger than region size."
                    )
                padding_width = output_size.width - data.shape[0]
                padding_height = output_size.height - data.shape[1]
                data = np.pad(data, ((0, padding_width), (0, padding_height), (0, 0)))  # type: ignore
            yield data
        finally:
            raw_data.release()

    def close(self) -> None:
        """Close reader pool."""
        self._reader_pool.close()

    def _read(
        self,
        image_index: int,
        resolution_index: int,
        index: int,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
    ) -> JArray:
        """Read image data from file."""
        with self._reader_pool.get_reader() as reader:
            reader.setSeries(image_index)
            reader.setResolution(resolution_index)
            return reader.openBytes(index, start_x, start_y, end_x, end_y)

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
