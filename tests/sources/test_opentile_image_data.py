#    Copyright 2026 SECTRA AB
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

"""Unit tests for OpenTileImageData."""

from pathlib import Path

import numpy as np
import pytest
from decoy import Decoy
from opentile.file import FrameReader
from opentile.geometry import Size
from opentile.jpeg2000 import Jpeg2000Info
from opentile.tiff_image import AssociatedTiffImage
from opentile.tile_byte_ranges import TileByteRanges as OpenTileTileByteRanges
from pydicom.uid import JPEG2000, UID, JPEG2000Lossless
from tifffile import PHOTOMETRIC
from wsidicom.codec import Encoder
from wsidicom.geometry import Point
from wsidicom.geometry import Size as WsiDicomSize
from wsidicom.instance import TileByteRanges

from wsidicomizer import WsiDicomizer
from wsidicomizer.sources.opentile.opentile_image_data import (
    OpenTileAssociatedImageData,
)


@pytest.mark.unittest
class TestOpenTileImageData:
    @pytest.mark.parametrize(
        [
            "reversible",
            "uses_mct",
            "subsampling",
            "expected_transfer_syntax",
            "expected_photometric_interpretation",
        ],
        [
            # Colour transform inside the codestream: YBR_ICT/YBR_RCT.
            (False, True, (1, 1), JPEG2000, "YBR_ICT"),
            (True, True, (1, 1), JPEG2000Lossless, "YBR_RCT"),
            # Colour transform outside the codestream, no subsampling: YBR_FULL.
            (False, False, (1, 1), JPEG2000, "YBR_FULL"),
            (True, False, (1, 1), JPEG2000Lossless, "YBR_FULL"),
            (False, False, None, JPEG2000, "YBR_FULL"),
            # Colour transform outside the codestream, subsampled chroma:
            # YBR_FULL_422 (e.g. Aperio 33003), which also covers 4:2:0.
            (False, False, (2, 1), JPEG2000, "YBR_FULL_422"),
            (False, False, (2, 2), JPEG2000, "YBR_FULL_422"),
            (True, False, (2, 1), JPEG2000Lossless, "YBR_FULL_422"),
        ],
    )
    def test_photometric_interpretation_of_ycbcr_jpeg2000(
        self,
        decoy: Decoy,
        reversible: bool,
        uses_mct: bool,
        subsampling: tuple[int, int] | None,
        expected_transfer_syntax: UID,
        expected_photometric_interpretation: str,
    ):
        # Arrange
        tiff_image = decoy.mock(cls=AssociatedTiffImage)
        decoy.when(tiff_image.photometric_interpretation).then_return(PHOTOMETRIC.YCBCR)
        decoy.when(tiff_image.encoded_info).then_return(
            Jpeg2000Info(
                reversible=reversible,
                uses_mct=uses_mct,
                components=3,
                subsampling=subsampling,
                bit_depth=8,
                extended=False,
            )
        )
        decoy.when(tiff_image.image_size).then_return(Size(512, 512))
        decoy.when(tiff_image.tile_size).then_return(Size(256, 256))
        decoy.when(tiff_image.tiled_size).then_return(Size(2, 2))
        decoy.when(tiff_image.pixel_spacing).then_return(None)
        encoder = decoy.mock(cls=Encoder)

        # Act
        image_data = OpenTileAssociatedImageData(tiff_image, encoder)

        # Assert
        assert image_data.transfer_syntax == expected_transfer_syntax
        assert (
            image_data.photometric_interpretation == expected_photometric_interpretation
        )

    def test_get_tile_byte_ranges_are_the_byte_ranges_of_opentile(self, decoy: Decoy):
        # Arrange
        tiff_image = self._create_jpeg2000_tiff_image(decoy)
        decoy.when(tiff_image.tile_byte_ranges).then_return(
            OpenTileTileByteRanges(
                positions=np.array([100, 200, 300, 400], dtype=np.int64),
                lengths=np.array(
                    [4, OpenTileTileByteRanges.READ_THROUGH_IMAGE, 4, 4], dtype=np.int64
                ),
            )
        )
        image_data = OpenTileAssociatedImageData(tiff_image, decoy.mock(cls=Encoder))

        # Act
        byte_ranges = image_data.get_tile_byte_ranges(
            image_data.default_z, image_data.default_path
        )

        # Assert
        assert byte_ranges is not None
        assert byte_ranges.tiled_size == WsiDicomSize(2, 2)
        assert byte_ranges.whole_tiled_size == WsiDicomSize(2, 2)
        assert byte_ranges.positions.tolist() == [100, 200, 300, 400]
        assert byte_ranges.lengths.tolist() == [
            4,
            TileByteRanges.READ_THROUGH_IMAGE_DATA,
            4,
            4,
        ]
        assert byte_ranges.file_indices is None

    def test_get_tile_byte_ranges_share_the_arrays_of_opentile(self, decoy: Decoy):
        """The byte ranges are views of the arrays of opentile rather than copies."""
        # Arrange
        opentile_byte_ranges = OpenTileTileByteRanges(
            positions=np.array([100, 200, 300, 400], dtype=np.int64),
            lengths=np.array([4, 4, 4, 4], dtype=np.int64),
        )
        tiff_image = self._create_jpeg2000_tiff_image(decoy)
        decoy.when(tiff_image.tile_byte_ranges).then_return(opentile_byte_ranges)
        image_data = OpenTileAssociatedImageData(tiff_image, decoy.mock(cls=Encoder))

        # Act
        byte_ranges = image_data.get_tile_byte_ranges(
            image_data.default_z, image_data.default_path
        )

        # Assert
        assert byte_ranges is not None
        assert np.shares_memory(
            np.asarray(byte_ranges.positions), opentile_byte_ranges.positions
        )
        assert np.shares_memory(
            np.asarray(byte_ranges.lengths), opentile_byte_ranges.lengths
        )

    def test_opentile_and_wsidicom_mark_tiles_to_read_through_alike(self):
        """Lengths of opentile are passed on as they are, which requires a tile to be
        read through the image to be marked with the same length by both."""
        # Arrange

        # Act
        opentile_mark = OpenTileTileByteRanges.READ_THROUGH_IMAGE
        wsidicom_mark = TileByteRanges.READ_THROUGH_IMAGE_DATA

        # Assert
        assert opentile_mark == wsidicom_mark

    def test_get_frame_readers_is_frame_reader_of_opentile(self, decoy: Decoy):
        # Arrange
        reader = decoy.mock(cls=FrameReader)
        tiff_image = self._create_jpeg2000_tiff_image(decoy)
        decoy.when(tiff_image.frame_reader).then_return(reader)
        image_data = OpenTileAssociatedImageData(tiff_image, decoy.mock(cls=Encoder))

        # Act
        readers = image_data.get_frame_readers()

        # Assert
        assert readers == [reader]

    @pytest.mark.parametrize(
        ["force_transcoding", "has_byte_ranges"], [(True, True), (False, False)]
    )
    def test_get_tile_byte_ranges_is_none_when_transcoding_or_not_located(
        self, decoy: Decoy, force_transcoding: bool, has_byte_ranges: bool
    ):
        # Arrange
        tiff_image = self._create_jpeg2000_tiff_image(decoy)
        decoy.when(tiff_image.tile_byte_ranges).then_return(
            OpenTileTileByteRanges(
                positions=np.zeros(4, dtype=np.int64),
                lengths=np.zeros(4, dtype=np.int64),
            )
            if has_byte_ranges
            else None
        )
        image_data = OpenTileAssociatedImageData(
            tiff_image, decoy.mock(cls=Encoder), force_transcoding
        )

        # Act
        byte_ranges = image_data.get_tile_byte_ranges(
            image_data.default_z, image_data.default_path
        )

        # Assert
        assert byte_ranges is None

    def test_read_encoded_tile_of_svs_is_encoded_tile_of_level(
        self, testdata_dir: Path
    ):
        """Tiles read with the tile byte ranges are those read through the level."""
        # Arrange
        slide = testdata_dir.joinpath("slides", "svs", "CMU-1", "CMU-1.svs")
        if not slide.exists():
            pytest.skip(f"{slide} not found")
        with WsiDicomizer.open(slide) as wsi:
            reads = [
                (level, Point(index % tiled_size.width, index // tiled_size.width))
                for level in wsi.levels
                for tiled_size in [level.default_instance.image_data.tiled_size]
                for index in range(0, tiled_size.area, max(1, tiled_size.area // 50))
            ]

            # Act
            mismatches = [
                (level.level, tile)
                for level, tile in reads
                if wsi.read_encoded_tile(level.level, tile.to_tuple())
                != level.get_encoded_tile(tile)
            ]

        # Assert
        assert mismatches == []

    @staticmethod
    def _create_jpeg2000_tiff_image(decoy: Decoy) -> AssociatedTiffImage:
        """A 2 x 2 tiled image of JPEG 2000 tiles, which are served as they are."""
        tiff_image = decoy.mock(cls=AssociatedTiffImage)
        decoy.when(tiff_image.photometric_interpretation).then_return(PHOTOMETRIC.RGB)
        decoy.when(tiff_image.encoded_info).then_return(
            Jpeg2000Info(
                reversible=False,
                uses_mct=True,
                components=3,
                subsampling=(1, 1),
                bit_depth=8,
                extended=False,
            )
        )
        decoy.when(tiff_image.image_size).then_return(Size(512, 512))
        decoy.when(tiff_image.tile_size).then_return(Size(256, 256))
        decoy.when(tiff_image.tiled_size).then_return(Size(2, 2))
        decoy.when(tiff_image.pixel_spacing).then_return(None)
        decoy.when(tiff_image.focal_plane).then_return(0.0)
        decoy.when(tiff_image.optical_path).then_return("0")
        return tiff_image
