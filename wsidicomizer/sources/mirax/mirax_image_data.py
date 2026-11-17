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

"""Image data for the MIRAX (.mrxs) base level, composed from MiraxReader's tiles."""

import numpy as np
from opentile.geometry import Point as OpenTilePoint
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Region
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.thread import ReadExecutor

from wsidicomizer.image_data import ComposedLevelImageData
from wsidicomizer.sources.mirax.reader import MiraxReader


class MiraxLevelImageData(ComposedLevelImageData):
    """The brightfield MIRAX base level (RGB), composed from the stored tiles."""

    def __init__(
        self,
        mrxs: MiraxReader,
        image_metadata: ImageMetadata,
        tile_size: int | None,
        encoder: Encoder,
    ):
        """Wrap the brightfield MIRAX base level as ImageData.

        Parameters
        ----------
        mrxs: MiraxReader
            The reader to read tiles from; its fill color is the background.
        image_metadata: ImageMetadata
            Image metadata for the level.
        tile_size: int | None
            Output tile size. If None, the default tile size is used.
        encoder: Encoder
            Encoder to use.
        """
        super().__init__(
            mrxs.overlap,
            np.array(mrxs.fill_color, dtype=mrxs.dtype),
            image_metadata,
            tile_size,
            mrxs.fill_color,
            encoder,
        )
        self._mrxs = mrxs

    def _decode_tile(self, grid_position: OpenTilePoint) -> np.ndarray:
        return self._mrxs.decode_tile(grid_position)


class MiraxFluorescenceLevelImageData(ComposedLevelImageData):
    """The fluorescence MIRAX base level: each channel is a separate grayscale
    (MONOCHROME2) optical path, the channel's band of the composed packed tiles.
    Grayscale is 8- or 16-bit per the slide's depth."""

    def __init__(
        self,
        mrxs: MiraxReader,
        image_metadata: ImageMetadata,
        tile_size: int | None,
        encoder: Encoder,
    ):
        """Wrap the fluorescence MIRAX base level as ImageData.

        Parameters
        ----------
        mrxs: MiraxReader
            The reader to read tiles from; its fill color is the background.
        image_metadata: ImageMetadata
            Image metadata for the level.
        tile_size: int | None
            Output tile size. If None, the default tile size is used.
        encoder: Encoder
            Encoder to use (grayscale/MONOCHROME2).
        """
        fill = np.array(mrxs.fill_color, dtype=mrxs.dtype)
        # the blank color of the grayscale level is the fill of its first channel;
        # each channel's blank tiles are filled with that channel's fill
        super().__init__(
            mrxs.overlap,
            fill,
            image_metadata,
            tile_size,
            int(fill[mrxs.channels[0].band]),
            encoder,
        )
        self._mrxs = mrxs
        self._channels = mrxs.channels
        # optical path identifiers = the fluorophore channel names
        self._optical_paths = [channel.name for channel in mrxs.channels]

    @property
    def samples_per_pixel(self) -> int:
        return 1

    @property
    def optical_paths(self) -> list[str]:
        return self._optical_paths

    def get_decoded_region(
        self,
        region: Region,
        z: float,
        path: str,
        *,
        executor: ReadExecutor | None = None,
    ) -> np.ndarray:
        """Read one channel's grayscale intensity over a region.

        Parameters
        ----------
        region: Region
            Pixel region to read.
        z: float
            Z coordinate.
        path: str
            Optical path (channel) to read.
        executor: ReadExecutor | None
            Per-read parallelism policy the tile decode fans out across (>1 worker
            for viewing), or None on the conversion path.

        Returns
        -------
        np.ndarray
            The channel's ``(rows, columns)`` intensity (uint8 or uint16).
        """
        return self._read_channel(region, z, path, executor)

    def get_decoded_tile(
        self, tile_point: Point, z: float, path: str, cache: bool = True
    ) -> np.ndarray:
        """Return a channel's grayscale tile.

        Parameters
        ----------
        tile_point: Point
            Tile position to get.
        z: float
            Focal plane of the tile.
        path: str
            Optical path (channel) of the tile.
        cache: bool = True
            Unused; the reader caches decoded source tiles itself.

        Returns
        -------
        np.ndarray
            The tile's ``(rows, columns)`` intensity (uint8 or uint16).
        """
        region = Region(tile_point * self.tile_size, self.tile_size)
        return self._read_channel(region, z, path)

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
        data = self._read_channel(region, z, path)
        fill = self._channel_fill(path)
        if self._detect_blank_tile(data, fill):
            return self._get_blank_encoded_frame(self.tile_size, fill)
        return self.encoder.encode(data)

    def _decode_tile(self, grid_position: OpenTilePoint) -> np.ndarray:
        return self._mrxs.decode_tile(grid_position)

    def _band(self, path: str) -> int:
        """The band of the packed tiles a channel is stored in.

        Parameters
        ----------
        path: str
            Optical path (channel).

        Returns
        -------
        int
            The channel's band.
        """
        return self._channels[self._optical_paths.index(path)].band

    def _channel_fill(self, path: str) -> int:
        """The slide's stated fill value (IMAGE_FILL_COLOR_BGR) in a channel's band.

        Parameters
        ----------
        path: str
            Optical path (channel).

        Returns
        -------
        int
            The fill value empty areas of the channel read as.
        """
        return int(self._fill[self._band(path)])

    def _read_channel(
        self, region: Region, z: float, path: str, executor: ReadExecutor | None = None
    ) -> np.ndarray:
        """Return one channel's (H, W) intensity array for a region.

        Parameters
        ----------
        region: Region
            Region to read.
        z: float
            Focal plane to read.
        path: str
            Optical path (channel) to read.
        executor: ReadExecutor | None
            Per-read parallelism policy the tile decode fans out across, or None.

        Returns
        -------
        np.ndarray
            The channel's (H, W) intensity (uint8 or uint16).
        """
        self._check_z_and_path(z, path)
        return self._compose(region, executor)[:, :, self._band(path)]
