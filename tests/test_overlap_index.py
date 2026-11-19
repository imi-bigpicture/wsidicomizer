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

"""Tests for the spatial index over overlapping tile placements (no slide needed)."""

import pytest
from opentile.geometry import Point, PointF, Region, Size
from opentile.tile_overlap import TileOverlap, TilePlacement

from wsidicomizer.overlap_index import OverlapIndex


@pytest.mark.unittest
class TestOverlapIndex:
    @pytest.mark.parametrize("whole_tile", [4], indirect=True)
    def test_piece_found_in_bucket_of_its_last_pixel(self, whole_tile: Region):
        # Arrange - a 4 px placement at x = 49 reaches pixel 52, in bucket 13 of 4 px
        # buckets
        overlap = TileOverlap(
            Size(64, 4), {Point(0, 0): [TilePlacement(whole_tile, PointF(49, 0))]}
        )
        index = OverlapIndex(overlap, bucket_size=4)

        # Act
        found = index.placements_in(Region(Point(52, 0), Size(1, 1)))

        # Assert
        assert [placement.position for placement in found] == [Point(49, 0)]

    @pytest.mark.parametrize("whole_tile", [4], indirect=True)
    def test_fractional_position_is_refused(self, whole_tile: Region):
        # Arrange - a placement at x = 48.75, as on a stored lower-resolution level
        overlap = TileOverlap(
            Size(64, 4), {Point(0, 0): [TilePlacement(whole_tile, PointF(48.75, 0))]}
        )

        # Act / Assert
        with pytest.raises(ValueError, match="fractional"):
            OverlapIndex(overlap)

    @pytest.mark.parametrize("whole_tile", [20], indirect=True)
    def test_placements_sorted_by_grid_row_then_column_and_listed_once(
        self, whole_tile: Region
    ):
        # Arrange - placements spanning several buckets, given out of order
        overlap = TileOverlap(
            Size(40, 40),
            {
                Point(1, 1): [TilePlacement(whole_tile, PointF(18, 18))],
                Point(1, 0): [TilePlacement(whole_tile, PointF(18, 0))],
                Point(0, 1): [TilePlacement(whole_tile, PointF(0, 18))],
                Point(0, 0): [TilePlacement(whole_tile, PointF(0, 0))],
            },
        )
        index = OverlapIndex(overlap, bucket_size=8)

        # Act
        found = index.placements_in(Region(Point(0, 0), Size(40, 40)))

        # Assert
        assert [placement.tile for placement in found] == [
            Point(0, 0),
            Point(1, 0),
            Point(0, 1),
            Point(1, 1),
        ]

    @pytest.mark.parametrize("whole_tile", [20], indirect=True)
    def test_grid_order_not_placed_position_decides(self, whole_tile: Region):
        # Arrange - two tiles of one grid row, the right-hand one placed 2 px
        # higher, as photos placed from recorded camera positions can be
        overlap = TileOverlap(
            Size(40, 22),
            {
                Point(0, 0): [TilePlacement(whole_tile, PointF(0, 2))],
                Point(1, 0): [TilePlacement(whole_tile, PointF(18, 0))],
            },
        )
        index = OverlapIndex(overlap, bucket_size=8)

        # Act
        found = index.placements_in(Region(Point(0, 0), Size(40, 22)))

        # Assert - the right-hand tile is pasted last, so it wins the overlap
        assert [placement.tile for placement in found] == [Point(0, 0), Point(1, 0)]
