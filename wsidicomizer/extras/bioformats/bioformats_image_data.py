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

"""Image data read by bioformats."""

from pathlib import Path
from typing import ContextManager, List, Optional

import numpy as np
from PIL import Image as Pillow
from PIL.Image import Image
from pydicom.uid import UID
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Region, Size, SizeMm

from wsidicomizer.extras.bioformats.bioformats_reader import BioformatsReader
from wsidicomizer.image_data import DicomizerImageData


class BioformatsImageData(DicomizerImageData):
    def __init__(
        self,
        reader: BioformatsReader,
        tile_size: int,
        encoder: Encoder,
        image_index: int,
        resolution_index: int,
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
        return self.encoder.transfer_syntax

    @property
    def image_size(self) -> Size:
        """Return the pixel size of the image."""
        return self._image_reader.size(self._image_index, self._resolution_index)

    @property
    def tile_size(self) -> Size:
        """Return the pixel tile size of the image, or pixel size of
        the image if not tiled."""
        return self._tile_size

    @property
    def pixel_spacing(self) -> Optional[SizeMm]:
        """Return the size of the pixels in mm/pixel."""
        return self._image_reader.pixel_spacing(
            self._image_index, self._resolution_index
        )

    @property
    def samples_per_pixel(self) -> int:
        """Return number of samples per pixel (e.g. 3 for RGB)."""
        return self._image_reader.samples_per_pixel(self._image_index)

    @property
    def photometric_interpretation(self) -> str:
        """Return the photophotometric interpretation of the image
        data."""
        return self.encoder.photometric_interpretation

    def _get_tile(
        self, tile_point: Point, z: float, path: str
    ) -> ContextManager[np.ndarray]:
        region = Region(tile_point * self.tile_size, self.tile_size)
        cropped_region = self.image_region.crop(region)
        return self._image_reader.read_image(
            self._image_index, self._resolution_index, cropped_region, self.tile_size
        )

    def _get_decoded_tile(self, tile: Point, z: float, path: str) -> Image:
        """Return Image for tile defined by tile (x, y), z,
        and optical path."""
        with self._get_tile(tile, z, path) as data:
            return Pillow.fromarray(data)

    def _get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return image bytes for tile defined by tile (x, y), z,
        and optical path."""
        with self._get_tile(tile, z, path) as data:
            return self.encoder.encode(data)

    @staticmethod
    def detect_format(filepath: Path) -> bool:
        return BioformatsReader.is_supported(filepath)
