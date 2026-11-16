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

"""Spatial index over the placements of a level whose stored tiles overlap.

A level whose stored tiles overlap (MIRAX, Ventana and similar) is described by an
opentile `TileOverlap`: each stored tile contributes one or more placements, a
region of the decoded tile at a position on the de-overlapped canvas.
`OverlapIndex` finds the placements under a region, in the order to paste them.

Only whole-pixel positions are indexed, as on base levels. The stored
lower-resolution levels of these formats place tiles at fractional positions, and
the pyramid is rebuilt from the base level instead.
"""

from dataclasses import dataclass

from opentile.geometry import Point, Region
from opentile.tile_overlap import TileOverlap


@dataclass(frozen=True)
class Placement:
    """A region of a stored tile placed on the de-overlapped canvas."""

    tile: Point
    """Grid position of the stored tile the placed region is cut from."""
    source: Region
    """Region of the decoded stored tile that is placed."""
    position: Point
    """Top-left of the placement on the canvas."""


class OverlapIndex:
    """Spatial index over the placements of a `TileOverlap`.

    Placements are bucketed on a grid over the canvas, so a query touches only the
    placements near the queried region instead of all placements of the level.
    """

    def __init__(self, overlap: TileOverlap, bucket_size: int = 512):
        """Index the placements of a level.

        Parameters
        ----------
        overlap: TileOverlap
            Placement of the level's stored tiles on the de-overlapped canvas.
        bucket_size: int = 512
            Edge of the square buckets, in canvas pixels.

        Raises
        ------
        ValueError
            If a tile is placed at a fractional position.
        """
        self._bucket_size = bucket_size
        self._buckets: dict[tuple[int, int], list[Placement]] = {}
        for tile, tile_placements in overlap.placements.items():
            for tile_placement in tile_placements:
                x, y = tile_placement.position.x, tile_placement.position.y
                if not (float(x).is_integer() and float(y).is_integer()):
                    raise ValueError(
                        f"Tile {tile} is placed at fractional position "
                        f"({x}, {y}); only whole-pixel positions are composed."
                    )
                self._insert(
                    Placement(tile, tile_placement.source, Point(int(x), int(y)))
                )

    def _insert(self, placement: Placement) -> None:
        """Add a placement to every bucket it overlaps.

        Parameters
        ----------
        placement: Placement
            The placement to add.
        """
        size = self._bucket_size
        x, y = placement.position.x, placement.position.y
        width, height = placement.source.size.width, placement.source.size.height
        for bucket_x in range(x // size, (x + width - 1) // size + 1):
            for bucket_y in range(y // size, (y + height - 1) // size + 1):
                self._buckets.setdefault((bucket_x, bucket_y), []).append(placement)

    def placements_in(self, region: Region) -> list[Placement]:
        """Return the placements overlapping a region, in compose order.

        Parameters
        ----------
        region: Region
            Canvas region to query.

        Returns
        -------
        list[Placement]
            The overlapping placements sorted by their stored tile's grid row,
            then column, so that pasting them in order lets the lower and the
            right-hand tile win an overlap, the same way for every region. The
            grid, not the placed position: tiles placed from recorded camera
            positions sit a few pixels apart, and ordering by position would let
            that jitter decide. The placed position breaks ties between the
            placements of one stored tile.
        """
        size = self._bucket_size
        left, top = region.start.x, region.start.y
        right, bottom = left + region.size.width, top + region.size.height
        # a placement spanning several buckets is found once per bucket
        found: set[Placement] = set()
        for bucket_x in range(left // size, (right - 1) // size + 1):
            for bucket_y in range(top // size, (bottom - 1) // size + 1):
                for placement in self._buckets.get((bucket_x, bucket_y), ()):
                    x, y = placement.position.x, placement.position.y
                    if (
                        x + placement.source.size.width <= left
                        or x >= right
                        or y + placement.source.size.height <= top
                        or y >= bottom
                    ):
                        continue
                    found.add(placement)
        return sorted(
            found,
            key=lambda p: (p.tile.y, p.tile.x, p.position.y, p.position.x),
        )
