#    Copyright 2021, 2022, 2023 SECTRA AB
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

from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from opentile import OpenTile
from opentile.common import OpenTilePage
from opentile.metadata import Metadata
from PIL import Image
from pydicom import Dataset
from pydicom.uid import JPEG2000, UID, JPEG2000Lossless, JPEGBaseline8Bit
from tifffile.tifffile import COMPRESSION, PHOTOMETRIC
from wsidicom.geometry import Point, Size, SizeMm, PointMm
from wsidicom.image_data import ImageOrigin

from wsidicomizer.base_dicomizer import BaseDicomizer
from wsidicomizer.image_data import DicomizerImageData
from wsidicomizer.encoding import Encoder


class OpenTileImageData(DicomizerImageData):
    def __init__(
        self,
        tiled_page: OpenTilePage,
        encoder: Encoder,
        image_offset: Optional[Tuple[float, float]] = None
    ):
        """Wraps a OpenTilePage to ImageData.

        Parameters
        ----------
        tiled_page: OpenTilePage
            OpenTilePage to wrap.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(encoder)
        self._tiled_page = tiled_page

        self._needs_transcoding = not self.is_supported_transfer_syntax()
        if self.needs_transcoding:
            self._transfer_syntax = self._encoder.transfer_syntax
        else:
            self._transfer_syntax = self.get_transfer_syntax()
        self._image_size = Size(*self._tiled_page.image_size.to_tuple())
        self._tile_size = Size(*self._tiled_page.tile_size.to_tuple())
        self._tiled_size = Size(*self._tiled_page.tiled_size.to_tuple())
        if self._tiled_page.pixel_spacing is not None:
            self._pixel_spacing = SizeMm(
                *self._tiled_page.pixel_spacing.to_tuple()
            )
        else:
            self._pixel_spacing = None
        # if image_offset is not None:
        #     self._image_origin = ImageOrigin(
        #         origin=PointMm(image_offset[0], image_offset[1])
        #     )
        # else:
        self._image_origin = ImageOrigin()

    def __str__(self) -> str:
        return f"{type(self).__name__} for page {self._tiled_page}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._tiled_page})"

    @property
    def files(self) -> List[Path]:
        return [Path(self._tiled_page.filepath)]

    @property
    def transfer_syntax(self) -> UID:
        """The uid of the transfer syntax of the image."""
        return self._transfer_syntax

    @property
    def needs_transcoding(self) -> bool:
        """Return true if image data requires transcoding for Dicom
        compatibilty."""
        return self._needs_transcoding

    @property
    def native_compression(self) -> COMPRESSION:
        """Return compression method used in image data."""
        return self._tiled_page.compression

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @property
    def pixel_spacing(self) -> Optional[SizeMm]:
        """Size of the pixels in mm/pixel."""
        return self._pixel_spacing

    @property
    def focal_planes(self) -> List[float]:
        """Focal planes avaiable in the image defined in um."""
        return [self._tiled_page.focal_plane]

    @property
    def optical_paths(self) -> List[str]:
        """Optical paths avaiable in the image."""
        return [self._tiled_page.optical_path]

    @property
    def suggested_minimum_chunk_size(self) -> int:
        """Return suggested minumum chunk size for optimal performance with
        get_encoeded_tiles()."""
        return self._tiled_page.suggested_minimum_chunk_size

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return self._tiled_page.pyramid_index

    @property
    def image_origin(self) -> ImageOrigin:
        return self._image_origin

    @property
    def photometric_interpretation(self) -> str:
        if self.needs_transcoding:
            return self._encoder.photometric_interpretation(
                self.samples_per_pixel
            )
        if self._tiled_page.photometric_interpretation == PHOTOMETRIC.YCBCR:
            if self.transfer_syntax == JPEGBaseline8Bit:
                return 'YBR_FULL_422'
            elif self.transfer_syntax == JPEG2000:
                return 'YBR_ICT'
            elif self.transfer_syntax == JPEG2000Lossless:
                return 'YBR_RCT'
        elif self._tiled_page.photometric_interpretation == PHOTOMETRIC.RGB:
            return 'RGB'
        elif self._tiled_page.photometric_interpretation == (
            PHOTOMETRIC.MINISBLACK
        ):
            return 'MONOCHROME2'
        raise NotImplementedError(
            "Non-implemented photometric interpretation. ",
            self._tiled_page.photometric_interpretation
        )

    @property
    def samples_per_pixel(self) -> int:
        return self._tiled_page.samples_per_pixel

    def _get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return image bytes for tile. Returns transcoded tile if
        non-supported encoding.

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
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError()
        if self.needs_transcoding:
            decoded_tile = self._tiled_page.get_decoded_tile(tile.to_tuple())
            return self._encode(decoded_tile)
        return self._tiled_page.get_tile(tile.to_tuple())

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
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        return Image.fromarray(
            self._tiled_page.get_decoded_tile(tile.to_tuple())
        )

    def get_encoded_tiles(
        self,
        tiles: Sequence[Point],
        z: float,
        path: str
    ) -> List[bytes]:
        """Return list of image bytes for tiles. Returns transcoded tiles if
        non-supported encoding.

        Parameters
        ----------
        tiles: Sequence[Point]
            Tile positions to get.
        z: float
            Focal plane of tile to get.
        path: str
            Optical path of tile to get.

        Returns
        ----------
        Iterator[List[bytes]]
            Iterator of tile bytes.
        """
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        tiles_tuples = [tile.to_tuple() for tile in tiles]
        if not self.needs_transcoding:
            return self._tiled_page.get_tiles(tiles_tuples)
        decoded_tiles = self._tiled_page.get_decoded_tiles(tiles_tuples)
        return [self._encode(tile) for tile in decoded_tiles]

    def close(self) -> None:
        self._tiled_page.close()

    def is_supported_transfer_syntax(self) -> bool:
        """Return true if image data is encoded with Dicom-supported transfer
        syntax."""
        try:
            self.get_transfer_syntax()
            return True
        except NotImplementedError:
            return False

    def get_transfer_syntax(self) -> UID:
        """Return transfer syntax (Uid) for compression type in image data."""
        compression = self.native_compression
        if compression == COMPRESSION.JPEG:
            return JPEGBaseline8Bit
        elif compression == COMPRESSION.APERIO_JP2000_RGB:
            return JPEG2000
        raise NotImplementedError(
            f'Not supported compression {compression}'
        )


class OpenTileDicomizer(BaseDicomizer):
    def __init__(
        self,
        filepath: Path,
        encoder: Encoder,
        tile_size: int,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        include_confidential: bool = True,
    ) -> None:
        self._tiler = OpenTile.open(filepath, tile_size)
        self._metadata = self._tiler.metadata
        super().__init__(
            filepath,
            encoder,
            tile_size,
            modules,
            include_confidential
        )

    @property
    def has_label(self) -> bool:
        return len(self._tiler.labels) > 0

    @property
    def has_overview(self) -> bool:
        return len(self._tiler.overviews) > 0

    @property
    def metadata(self) -> Metadata:
        return self._metadata

    @property
    def pyramid_levels(self) -> List[int]:
        return [level.pyramid_index for level in self._tiler.levels]

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """Return True if file in filepath is supported by OpenTile."""
        return OpenTile.detect_format(filepath) is not None

    def _create_level_image_data(self, level_index: int) -> DicomizerImageData:
        level = self._tiler.levels[level_index]
        return OpenTileImageData(level, self._encoder)

    def _create_label_image_data(self) -> DicomizerImageData:
        label = self._tiler.labels[0]
        return OpenTileImageData(label, self._encoder)

    def _create_overview_image_data(self) -> DicomizerImageData:
        overview = self._tiler.overviews[0]
        return OpenTileImageData(overview, self._encoder)
