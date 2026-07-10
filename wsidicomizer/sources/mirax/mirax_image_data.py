#    Copyright 2025 SECTRA AB
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

"""Image data for a MIRAX (.mrxs) level, backed by MiraxReader."""

import numpy as np
from PIL import Image as Pillow
from PIL.Image import Image
from wsidicom.codec import Encoder
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, Region
from wsidicom.metadata import Image as ImageMetadata

from wsidicomizer.sources.mirax.reader import MiraxReader
from wsidicomizer.sources.openslide_like import OpenSlideLikeLevelImageData


class MiraxLevelImageData(OpenSlideLikeLevelImageData):
    """A brightfield MIRAX pyramid level (RGB). Reuses OpenSlideLikeLevelImageData
    for sizing and pixel spacing; only the pixel read differs. MiraxReader is
    level-local, so there's no level-0-location downsample/offset dance."""

    def __init__(
        self,
        mrxs: MiraxReader,
        blank_color: int | tuple[int, int, int] | None,
        image_metadata: ImageMetadata,
        level_index: int,
        tile_size: int | None,
        encoder: Encoder,
    ):
        """Wrap a brightfield MIRAX pyramid level as ImageData.

        Parameters
        ----------
        mrxs: MiraxReader
            The reader to read tiles from.
        blank_color: int | tuple[int, int, int] | None
            Background color for empty regions.
        image_metadata: ImageMetadata
            Image metadata for the level.
        level_index: int
            Level in the reader to wrap.
        tile_size: int | None
            Output tile size. If None, the default tile size is used.
        encoder: Encoder
            Encoder to use.
        """
        super().__init__(
            blank_color,
            None,  # offset: the reader origin is already the tissue bounding box
            None,  # size: use the reader's own level_dimensions
            mrxs.level_dimensions,
            mrxs.level_downsamples,
            image_metadata,
            level_index,
            tile_size,
            encoder,
        )
        self._mrxs = mrxs

    def read_region(self, region: Region, z: float, path: str) -> Image:
        """Read a pixel region from the reader as a Pillow image.

        Parameters
        ----------
        region: Region
            Pixel region to read.
        z: float
            Z coordinate.
        path: str
            Optical path.

        Returns
        -------
        Image
            The region as a Pillow image.
        """
        self._check_z_and_path(z, path)
        data = self._get_region(region)
        if data is None:
            return self._get_blank_decoded_frame(region.size)
        return Pillow.fromarray(data)

    def get_decoded_tile(self, tile_point: Point, z: float, path: str) -> Image:
        """Return an RGB Image for a tile.

        Parameters
        ----------
        tile_point: Point
            Tile position to get.
        z: float
            Focal plane of the tile.
        path: str
            Optical path of the tile.

        Returns
        -------
        Image
            The tile as a Pillow image.
        """
        self._check_z_and_path(z, path)
        tile = self._get_region(Region(tile_point * self.tile_size, self.tile_size))
        if tile is None:
            return self._get_blank_decoded_frame(self.tile_size)
        return Pillow.fromarray(tile)

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return the encoded bytes for a tile.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        z: float
            Focal plane of the tile.
        path: str
            Optical path of the tile.

        Returns
        -------
        bytes
            The encoded tile.
        """
        self._check_z_and_path(z, path)
        decoded = self._get_region(Region(tile * self.tile_size, self.tile_size))
        if decoded is None:
            return self._get_blank_encoded_frame(self.tile_size)
        return self.encoder.encode(decoded)

    def _check_z_and_path(self, z: float, path: str) -> None:
        """Raise if `z` or `path` is not available on this level.

        Parameters
        ----------
        z: float
            Focal plane to check.
        path: str
            Optical path to check.
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))

    def _get_region(self, region: Region) -> np.ndarray | None:
        """Return the region pixels as an RGB array, or None when all fill.

        Parameters
        ----------
        region: Region
            Region to read.

        Returns
        -------
        np.ndarray | None
            The region's RGB pixels, or None if the region is blank.
        """
        if region.size.width < 0 or region.size.height < 0:
            raise ValueError("Negative size not allowed")
        data = self._mrxs.read_region(
            self._level_index, region.start.to_tuple(), region.size.to_tuple()
        )
        if self._detect_blank_tile(data):
            return None
        return data


class MiraxFluorescenceLevelImageData(OpenSlideLikeLevelImageData):
    """A fluorescence MIRAX level: each channel is a separate grayscale
    (MONOCHROME2) optical path, split out of the packed tile by
    MiraxReader.read_channel. Grayscale is 8- or 16-bit per the slide's depth.
    Reuses OpenSlideLikeLevelImageData for sizing."""

    def __init__(
        self,
        mrxs: MiraxReader,
        blank_color: int | tuple[int, int, int] | None,
        image_metadata: ImageMetadata,
        level_index: int,
        tile_size: int | None,
        encoder: Encoder,
    ):
        """Wrap a fluorescence MIRAX level as ImageData.

        Parameters
        ----------
        mrxs: MiraxReader
            The reader to read channels from.
        blank_color: int | tuple[int, int, int] | None
            Background color for empty regions.
        image_metadata: ImageMetadata
            Image metadata for the level.
        level_index: int
            Level in the reader to wrap.
        tile_size: int | None
            Output tile size. If None, the default tile size is used.
        encoder: Encoder
            Encoder to use (grayscale/MONOCHROME2).
        """
        super().__init__(
            blank_color,
            None,
            None,
            mrxs.level_dimensions,
            mrxs.level_downsamples,
            image_metadata,
            level_index,
            tile_size,
            encoder,
        )
        self._mrxs = mrxs
        # optical path identifiers = the fluorophore channel names
        self._optical_paths = [channel.name for channel in mrxs.channels]

    @property
    def samples_per_pixel(self) -> int:
        return 1

    @property
    def optical_paths(self) -> list[str]:
        return self._optical_paths

    def read_region(self, region: Region, z: float, path: str) -> Image:
        """Read one channel's grayscale intensity over a region.

        Parameters
        ----------
        region: Region
            Pixel region to read.
        z: float
            Z coordinate.
        path: str
            Optical path (channel) to read.

        Returns
        -------
        Image
            The channel's intensity as a single-band ("L" or "I;16") image.
        """
        return Pillow.fromarray(self._read_channel(region, z, path))

    def get_decoded_tile(self, tile_point: Point, z: float, path: str) -> Image:
        """Return a channel's grayscale tile.

        Parameters
        ----------
        tile_point: Point
            Tile position to get.
        z: float
            Focal plane of the tile.
        path: str
            Optical path (channel) of the tile.

        Returns
        -------
        Image
            The tile as a single-band ("L" or "I;16") image.
        """
        region = Region(tile_point * self.tile_size, self.tile_size)
        return Pillow.fromarray(self._read_channel(region, z, path))

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return a channel's encoded grayscale tile.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        z: float
            Focal plane of the tile.
        path: str
            Optical path (channel) of the tile.

        Returns
        -------
        bytes
            The encoded tile.
        """
        region = Region(tile * self.tile_size, self.tile_size)
        return self.encoder.encode(self._read_channel(region, z, path))

    def _read_channel(self, region: Region, z: float, path: str) -> np.ndarray:
        """Return one channel's (H, W) intensity array for a region.

        Parameters
        ----------
        region: Region
            Region to read.
        z: float
            Focal plane to read.
        path: str
            Optical path (channel) to read.

        Returns
        -------
        np.ndarray
            The channel's (H, W) intensity (uint8 or uint16).
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
        channel = self._optical_paths.index(path)
        return self._mrxs.read_channel(
            self._level_index,
            region.start.to_tuple(),
            region.size.to_tuple(),
            channel,
        )
