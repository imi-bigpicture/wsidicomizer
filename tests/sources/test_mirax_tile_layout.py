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

"""Tests for the MIRAX base-level tile layout (no slide needed)."""

import struct
from types import SimpleNamespace
from typing import Any, cast

import pytest
from opentile.geometry import Point, PointF, Size

from wsidicomizer.sources.mirax.reader.index import BlobLocation
from wsidicomizer.sources.mirax.reader.tile_layout import MiraxTileLayout

# 4x4 tiles, 2 tiles per camera photo edge, a 2x1 photo grid
SLIDEDAT = SimpleNamespace(
    tile_size=Size(4, 4),
    divisions=2,
    imagenumber_x=4,
    imagenumber_y=2,
    overlap=PointF(2, 2),
)
TILES = {Point(x, y): BlobLocation(0, 0, 0) for x in range(4) for y in range(2)}


def placed(layout: MiraxTileLayout) -> dict[tuple[int, int], tuple[float, float]]:
    """The (x, y) each tile is placed at, by grid position."""
    return {
        (point.x, point.y): (
            tile_placements[0].position.x,
            tile_placements[0].position.y,
        )
        for point, tile_placements in layout.overlap.placements.items()
    }


@pytest.mark.unittest
class TestMiraxTileLayout:
    def test_nominal_overlap_places_photos_apart_by_photo_size_less_overlap(self):
        # Act
        layout = MiraxTileLayout(TILES, cast(Any, SLIDEDAT), None)

        # Assert - the second photo starts at 2 * 4 - 2 = 6
        assert placed(layout) == {
            (0, 0): (0, 0),
            (1, 0): (4, 0),
            (2, 0): (6, 0),
            (3, 0): (10, 0),
            (0, 1): (0, 4),
            (1, 1): (4, 4),
            (2, 1): (6, 4),
            (3, 1): (10, 4),
        }
        assert layout.dimensions == Size(14, 8)

    def test_recorded_positions_place_photos_relative_to_tissue_bounds(self):
        # Arrange - photos recorded at (100, 50) and (105, 49)
        positions = struct.pack("<Bii", 1, 100, 50) + struct.pack("<Bii", 1, 105, 49)

        # Act
        layout = MiraxTileLayout(TILES, cast(Any, SLIDEDAT), positions)

        # Assert - the origin is the top-left of the tiles' bounding box
        assert layout.origin == Point(100, 49)
        assert placed(layout)[(0, 0)] == (0, 1)
        assert placed(layout)[(2, 0)] == (5, 0)
        assert layout.dimensions == Size(13, 9)

    def test_tile_of_unrecorded_photo_is_refused(self):
        # Arrange - the second photo has no recorded position
        positions = struct.pack("<Bii", 1, 0, 0) + struct.pack("<Bii", 0, 0, 0)

        # Act / Assert
        with pytest.raises(NotImplementedError):
            MiraxTileLayout(TILES, cast(Any, SLIDEDAT), positions)

    def test_slide_without_tiles_is_refused(self):
        # Arrange - an index with no base-level tiles, as an aborted scan has

        # Act / Assert
        with pytest.raises(NotImplementedError, match="without base-level tiles"):
            MiraxTileLayout({}, cast(Any, SLIDEDAT), None)
