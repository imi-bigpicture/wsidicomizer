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

import math
import os
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Condition

import jpype.imports  # noqa: F401  # pyright: ignore[reportUnusedImport]
import numpy as np
import ome_types
import scyjava
from jpype.types import JArray
from wsidicom.cache import lru_cached_method
from wsidicom.geometry import Region, Size, SizeMm

"""
Set version of bioformats jar to use with the environmental variable
"BIOFORMATS_VERSION". Note the bioformats jar either has a BSD or GPL-2
license.
"""
bioformats_version = os.getenv("BIOFORMATS_VERSION", "bsd:8.3.0")
scyjava.config.endpoints.append(f"ome:formats-{bioformats_version}")

if not scyjava.jvm_started():
    scyjava.start_jvm()

"""
Load bioformats modules using jpype and scyjava
"""
from loci.common.services import ServiceFactory  # type: ignore # noqa
from loci.formats import ImageReader, Memoizer  # type: ignore # noqa
from loci.formats.services import OMEXMLService  # type: ignore # noqa


class BioFormatsReaderPool:
    """A pool of reusable Bio-Formats readers. Concurrent leases never share a reader;
    `max_readers` caps how many may exist at once, so `max_readers=1` allows only
    one at a time.
    """

    def __init__(
        self,
        path: Path,
        max_readers: int | None = None,
        cache_path: Path | str | None = None,
    ) -> None:
        """Create a new BioFormatsReaderPool.

        Parameters
        ----------
        path: Path
            Path to file to open.
        max_readers: int | None
            Maximum number of readers that may exist concurrently. `None` (the
            default) is unbounded (bounded in practice by the number of
            concurrent callers).
        cache_path: Path | str | None
            Path to store cache file quicker opening of new readers. If `None`
            a temporary directory will be used.
        """
        self._filepath = path
        if cache_path is None:
            self._tempdir = TemporaryDirectory()
            self._cache_path = Path(self._tempdir.name)
        else:
            self._tempdir = None
            self._cache_path = Path(cache_path)
        self._max_readers = max_readers
        self._idle: deque[Memoizer] = deque()
        self._count = 0
        self._condition = Condition()

    @property
    def filepath(self) -> Path:
        return self._filepath

    @contextmanager
    def get_reader(self) -> Generator[Memoizer, None, None]:
        """Lease a reader for the duration of the context, blocking if none is free."""
        reader = self._acquire()
        try:
            yield reader
        finally:
            self._release(reader)

    def _create_new_reader(self) -> Memoizer:
        """Return a new reader."""
        # Create a reader using Memoizer to load file faster
        # See https://docs.openmicroscopy.org/bio-formats/6.11.0/developers/matlab-dev.html#reader-performance
        reader = Memoizer(ImageReader(), 0, self._cache_path)
        reader.setFlattenedResolutions(False)
        reader.setId(str(self._filepath))
        return reader

    def _acquire(self) -> Memoizer:
        """Return an idle reader, create a new one if under the bound, else block
        until a reader is released or discarded."""
        with self._condition:
            while not self._idle and not self._can_grow():
                self._condition.wait()
            if self._idle:
                return self._idle.popleft()
            self._count += 1
            try:
                return self._create_new_reader()
            except BaseException:
                self._count -= 1
                self._condition.notify()
                raise

    def _release(self, reader: Memoizer) -> None:
        """Return a reader to the idle set."""
        with self._condition:
            self._idle.append(reader)
            self._condition.notify()

    def _can_grow(self) -> bool:
        return self._max_readers is None or self._count < self._max_readers

    def close(self) -> None:
        """Close all idle readers. Call only when no readers are in use."""
        with self._condition:
            while self._idle:
                self._idle.popleft().close()
            self._count = 0
            if self._tempdir is not None:
                self._tempdir.cleanup()


class BioformatsReader:
    def __init__(
        self,
        filepath: Path,
        max_readers: int | None = None,
        cache_path: Path | str | None = None,
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
        if max_readers is None:
            cpu_count = os.cpu_count()
            max_readers = cpu_count if cpu_count is not None else 1
        self._reader_pool = BioFormatsReaderPool(
            path=filepath, max_readers=max_readers, cache_path=cache_path
        )

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        try:
            reader = ImageReader()
            reader.setId(str(filepath))
            reader.close()
        except Exception:
            return False
        return True

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
        """Return number of images in file."""
        return len(self.metadata.images)

    def image_name(self, image_index: int) -> str | None:
        """Return name of image."""
        return self.metadata.images[image_index].name

    @lru_cached_method()
    def dtype(self, image_index: int) -> np.dtype:
        """Return the numpy datatype for image in file."""
        NUMPY_DATA_TYPES: dict[str, type] = {
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
        byte_order = ">" if self.metadata.images[image_index].pixels.big_endian else "<"
        data_type = self.metadata.images[image_index].pixels.type.value
        try:
            numpy_data_type = np.dtype(NUMPY_DATA_TYPES[data_type])
        except KeyError as exception:
            raise ValueError(f"Unknown data type {data_type}") from exception
        return numpy_data_type.newbyteorder(byte_order)

    @lru_cached_method()
    def samples_per_pixel(self, image_index: int) -> int:
        """Return the samples per pixel for image in file."""
        pixels = self.metadata.images[image_index].pixels
        samples_per_pixel = pixels.channels[0].samples_per_pixel
        assert samples_per_pixel is not None
        return int(samples_per_pixel)

    @lru_cached_method()
    def size(self, image_index: int, resolution_index: int = 0) -> Size:
        """Return the image size for image in file."""
        with self._reader_pool.get_reader() as reader:
            reader.setSeries(image_index)
            reader.setResolution(resolution_index)
            width = reader.getSizeX()
            height = reader.getSizeY()
            return Size(int(width), int(height))

    @lru_cached_method()
    def pixel_spacing(
        self, image_index: int, resolution_index: int = 0
    ) -> SizeMm | None:
        """Return the size of the pixels in mm/pixel for image in file."""
        pixels = self.metadata.images[image_index].pixels
        if pixels.physical_size_x is None or pixels.physical_size_y is None:
            return None
        scale = self._resolution_scales(image_index)[resolution_index]
        return (
            SizeMm(float(pixels.physical_size_x), float(pixels.physical_size_y))
            * scale
            / 1000
        )

    @lru_cached_method()
    def is_interleaved(self, image_index: int) -> bool:
        """Return true if image data is interleaved."""
        interleaved = self.metadata.images[image_index].pixels.interleaved
        assert interleaved is not None
        return interleaved

    @lru_cached_method()
    def pyramid_levels(self, image_index: int) -> dict[tuple[int, float, str], int]:
        """Return dictionary of dyadic scaling, focal plane, and optical path as key
        and resolution index as value for resolutions in image.

        Focal planes and optical paths are not implemented.
        """
        TOLERANCE = 1e-2
        float_pyramid_levels = (
            math.log2(scale) for scale in self._resolution_scales(image_index)
        )
        return {
            (round(float_level), 0.0, "0"): resolution_index
            for resolution_index, float_level in enumerate(float_pyramid_levels)
            if math.isclose(float_level, round(float_level), abs_tol=TOLERANCE)
        }

    @lru_cached_method()
    def _resolution_scales(self, image_index: int) -> list[float]:
        """Return resolution scales for image.

        Scales are resolution width divided by image width.
        """
        with self._reader_pool.get_reader() as reader:
            reader.setSeries(image_index)
            reader.setResolution(0)
            base_width = reader.getSizeX()
            return [
                self._get_resolution_scale(reader, resolution_index, base_width)
                for resolution_index in range(reader.getResolutionCount())
            ]

    @staticmethod
    def _get_resolution_scale(
        reader: Memoizer, resolution_index: int, base_width: int
    ) -> float:
        """Return resolution scale for resolution as rounded int of resolution width
        divided by base width."""
        reader.setResolution(resolution_index)
        width = reader.getSizeX()
        return base_width / width

    @contextmanager
    def read_image(
        self,
        image_index: int,
        resolution_index: int,
        region: Region,
        output_size: Size | None = None,
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
        try:
            raw_data = memoryview(
                self._read(  # pyright: ignore[reportArgumentType]
                    image_index,
                    resolution_index,
                    index,
                    region.start.x,
                    region.start.y,
                    region.size.width,
                    region.size.height,
                )
            )
        except Exception as exception:
            raise Exception(
                f"Failed to read image data from image {image_index}, "
                f"resolution {resolution_index}, index {index} "
                f"at region {region.box}."
            ) from exception
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
                # Pad with zeros to get requested output size.
                if not output_size.all_greater_than_or_equal(region.size):
                    raise ValueError(
                        "Output size should be equal to or larger than region size."
                    )
                padding_width = output_size.width - data.shape[0]
                padding_height = output_size.height - data.shape[1]
                data = np.pad(data, ((0, padding_width), (0, padding_height), (0, 0)))
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
        with self._reader_pool.get_reader() as reader:
            metadata_store = reader.getMetadataStore()
            return str(metadata_store.dumpXML())
