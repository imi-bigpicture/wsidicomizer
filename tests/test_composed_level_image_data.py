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

"""Tests for composing a level whose stored tiles overlap (no slide needed)."""

import numpy as np
import pytest
from opentile.geometry import Point as OpenTilePoint
from opentile.geometry import PointF
from opentile.geometry import Region as OpenTileRegion
from opentile.geometry import Size as OpenTileSize
from opentile.tile_overlap import TileOverlap, TilePlacement
from wsidicom.codec import Encoder, JpegSettings
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata

from wsidicomizer.image_data import ComposedLevelImageData

BLACK = np.array([0, 0, 0], dtype=np.uint8)


class InMemoryComposedLevel(ComposedLevelImageData):
    """A composed level over tiles held in memory, recording what it decodes."""

    def __init__(
        self, overlap: TileOverlap, tiles: dict[OpenTilePoint, np.ndarray]
    ) -> None:
        super().__init__(
            overlap,
            BLACK,
            ImageMetadata(pixel_spacing=SizeMm(0.0005, 0.0005)),
            4,
            (0, 0, 0),
            Encoder.create_for_settings(JpegSettings()),
        )
        self._tiles = tiles
        self.decoded: list[OpenTilePoint] = []

    def _decode_tile(self, grid_position: OpenTilePoint) -> np.ndarray:
        self.decoded.append(grid_position)
        return self._tiles[grid_position]


@pytest.mark.unittest
class TestComposedLevelImageData:
    @pytest.mark.parametrize("whole_tile", [4], indirect=True)
    def test_overlapping_tiles_composed_later_wins(self, whole_tile: OpenTileRegion):
        # Arrange - two 4x4 tiles overlapping by 2 columns
        tiles = {
            OpenTilePoint(0, 0): np.full((4, 4, 3), 10, np.uint8),
            OpenTilePoint(1, 0): np.full((4, 4, 3), 20, np.uint8),
        }
        overlap = TileOverlap(
            OpenTileSize(6, 4),
            {
                OpenTilePoint(0, 0): [TilePlacement(whole_tile, PointF(0, 0))],
                OpenTilePoint(1, 0): [TilePlacement(whole_tile, PointF(2, 0))],
            },
        )
        image_data = InMemoryComposedLevel(overlap, tiles)

        # Act
        region = image_data.read_region(Region(Point(0, 0), Size(6, 4)), 0.0, "1")

        # Assert
        assert image_data.image_size == Size(6, 4)
        assert (region[:, :2] == 10).all()
        assert (region[:, 2:] == 20).all()

    def test_tile_placed_twice_is_decoded_once(self):
        # Arrange - one stored 4x2 tile packing two 2x2 regions placed apart
        tile = np.zeros((2, 4, 3), np.uint8)
        tile[:, :2], tile[:, 2:] = 1, 2
        overlap = TileOverlap(
            OpenTileSize(8, 4),
            {
                OpenTilePoint(0, 0): [
                    TilePlacement(
                        OpenTileRegion(OpenTilePoint(0, 0), OpenTileSize(2, 2)),
                        PointF(0, 0),
                    ),
                    TilePlacement(
                        OpenTileRegion(OpenTilePoint(2, 0), OpenTileSize(2, 2)),
                        PointF(5, 1),
                    ),
                ]
            },
        )
        image_data = InMemoryComposedLevel(overlap, {OpenTilePoint(0, 0): tile})

        # Act
        region = image_data.read_region(Region(Point(0, 0), Size(8, 4)), 0.0, "1")

        # Assert
        assert image_data.decoded == [OpenTilePoint(0, 0)]
        assert (region[0:2, 0:2] == 1).all()
        assert (region[1:3, 5:7] == 2).all()

    @pytest.mark.parametrize("whole_tile", [2], indirect=True)
    def test_composed_regions_are_independent(self, whole_tile: OpenTileRegion):
        # Arrange - a tile covering half of the region, the rest background
        overlap = TileOverlap(
            OpenTileSize(4, 2),
            {OpenTilePoint(0, 0): [TilePlacement(whole_tile, PointF(0, 0))]},
        )
        image_data = InMemoryComposedLevel(
            overlap, {OpenTilePoint(0, 0): np.full((2, 2, 3), 9, np.uint8)}
        )
        region = Region(Point(0, 0), Size(4, 2))
        first = image_data.read_region(region, 0.0, "1")

        # Act - mutate one composed region
        first[:] = 7

        # Assert - the background template is not corrupted
        second = image_data.read_region(region, 0.0, "1")
        assert (second[:, 2:] == 0).all()

    @pytest.mark.parametrize("whole_tile", [2], indirect=True)
    def test_region_without_tiles_is_blank(self, whole_tile: OpenTileRegion):
        # Arrange
        overlap = TileOverlap(
            OpenTileSize(8, 8),
            {OpenTilePoint(0, 0): [TilePlacement(whole_tile, PointF(0, 0))]},
        )
        image_data = InMemoryComposedLevel(
            overlap, {OpenTilePoint(0, 0): np.full((2, 2, 3), 9, np.uint8)}
        )

        # Act
        region = image_data.read_region(Region(Point(4, 4), Size(4, 4)), 0.0, "1")

        # Assert - no tile decoded, the region is the background
        assert image_data.decoded == []
        assert (region == 0).all()

    @pytest.mark.parametrize("whole_tile", [4], indirect=True)
    def test_region_offset_applied_and_tile_clipped(self, whole_tile: OpenTileRegion):
        # Arrange - a 4x4 tile at (10, 20), read through a region starting at
        # (12, 22) that holds only the tile's bottom-right quarter
        tile = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
        overlap = TileOverlap(
            OpenTileSize(16, 26),
            {OpenTilePoint(0, 0): [TilePlacement(whole_tile, PointF(10, 20))]},
        )
        image_data = InMemoryComposedLevel(overlap, {OpenTilePoint(0, 0): tile})

        # Act
        region = image_data.read_region(Region(Point(12, 22), Size(4, 4)), 0.0, "1")

        # Assert - the quarter lands in the top-left corner, the rest is background
        assert (region[:2, :2] == tile[2:, 2:]).all()
        assert (region[2:] == 0).all() and (region[:, 2:] == 0).all()
