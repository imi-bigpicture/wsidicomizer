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

from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from PIL import Image
from pydicom import Dataset
from pydicom.uid import JPEG2000, UID, JPEG2000Lossless, JPEGBaseline8Bit
from wsidicom import (WsiDicom, WsiDicomLabels, WsiDicomLevels,
                      WsiDicomOverviews, WsiInstance)
from wsidicom.geometry import Point, Size, SizeMm

from tifffile.tifffile import COMPRESSION, PHOTOMETRIC
from opentile import OpenTile
from opentile.common import OpenTilePage, Tiler
from wsidicomizer.common import MetaDicomizer, MetaImageData
from wsidicomizer.dataset import (create_base_dataset, populate_base_dataset)
from wsidicomizer.encoding import Encoder, create_encoder


class OpenTileImageData(MetaImageData):
    def __init__(
        self,
        tiled_page: OpenTilePage,
        encoder: Encoder
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


class OpenTileDicomizer(MetaDicomizer):
    @classmethod
    def open(
        cls,
        filepath: str,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        tile_size: int = 512,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '420'
    ) -> WsiDicom:
        """Open tiff file in filepath as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to tiff file
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: int = 512
            Tile size to use if not defined by file.
        include_levels: Sequence[int] = None
            Levels to include. If None, include all levels.
        include_label: bool = True
            Inclube label.
        include_overview: bool = True
            Include overview.
        include_confidential: bool = True
            Include confidential metadata.
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
            WsiDicom object of tiff file in filepath.
        """
        encoder = create_encoder(
            encoding_format,
            encoding_quality,
            subsampling=jpeg_subsampling
        )
        base_dataset = create_base_dataset(modules)
        tiler = OpenTile.open(filepath, tile_size)
        level_instances, label_instances, overview_instances = cls._open_tiler(
            tiler,
            encoder,
            base_dataset,
            include_levels=include_levels,
            include_label=include_label,
            include_overview=include_overview,
            include_confidential=include_confidential
        )
        levels = WsiDicomLevels.open(level_instances)
        labels = WsiDicomLabels.open(label_instances)
        overviews = WsiDicomOverviews.open(overview_instances)
        return cls(levels, labels, overviews)

    @staticmethod
    def is_supported(filepath: str) -> bool:
        """Return True if file in filepath is supported by OpenTile."""
        return OpenTile.detect_format(Path(filepath)) is not None

    @classmethod
    def _open_tiler(
        cls,
        tiler: Tiler,
        encoder: Encoder,
        base_dataset: Dataset,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True
    ) -> Tuple[List[WsiInstance], List[WsiInstance], List[WsiInstance]]:
        """Open tiler to produce WsiInstances.

        Parameters
        ----------
        tiler: Tiler
            Tiler that can produce WsiInstances.
        encoder: Encoder
            Encoder to use for re-encoding.
        base_dataset: Dataset
            Base dataset to include in files.
        include_levels: Optional[Sequence[int]] = None
            Optional list of levels to include. Include all levels if None.
        include_label: bool = True
            Include label(s), default true.
        include_overwiew: bool = True
            Include overview(s), default true.
        include_confidential: bool = True
            Include confidential metadata.

        Returns
        ----------
        Tuple[List[WsiInstance], List[WsiInstance], List[WsiInstance]]
            Lists of created level, label and overivew instances.
        """
        base_dataset = populate_base_dataset(
            tiler.metadata,
            base_dataset,
            include_confidential
        )
        instance_number = 0
        level_instances = [
            cls._create_instance(
                OpenTileImageData(level, encoder),
                base_dataset,
                'VOLUME',
                instance_number+index
            )
            for index, level in enumerate(tiler.levels)
            if cls._is_included_level(
                level.pyramid_index,
                [level.pyramid_index for level in tiler.levels],
                include_levels
            )
        ]
        instance_number += len(level_instances)
        label_instances = [
            cls._create_instance(
                OpenTileImageData(label, encoder),
                base_dataset,
                'LABEL',
                instance_number+index
            )
            for index, label in enumerate(tiler.labels)
            if include_label
        ]
        instance_number += len(level_instances)
        overview_instances = [
            cls._create_instance(
                OpenTileImageData(overview, encoder),
                base_dataset,
                'OVERVIEW',
                instance_number+index
            )
            for index, overview in enumerate(tiler.overviews)
            if include_overview
        ]

        return level_instances, label_instances, overview_instances
