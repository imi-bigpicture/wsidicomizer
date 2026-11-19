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

"""Places the MIRAX base-level tiles on the de-overlapped canvas.

Uses the recorded camera-photo positions when present (absolute, jitter-free);
otherwise the nominal per-photo OVERLAP_X/Y from Slidedat. Pure computation — the
caller reads the position-buffer bytes and passes them in.
"""

import struct

from opentile.geometry import Point, PointF, Region, Size
from opentile.tile_overlap import TileOverlap, TilePlacement

from wsidicomizer.sources.mirax.reader.index import BlobLocation
from wsidicomizer.sources.mirax.reader.slidedat import Slidedat


class MiraxTileLayout:
    """Layout of the base-level tiles: where each tile goes (an opentile
    `TileOverlap`), and the base level's origin and size.

    The origin (0,0) is the top-left of the scanned tissue bounding box, not the
    full glass slide. Base-level positions are whole pixels.
    """

    def __init__(
        self,
        tiles: dict[Point, BlobLocation],
        slidedat: Slidedat,
        position_bytes: bytes | None,
    ):
        """Compute the placement of the base-level tiles.

        Parameters
        ----------
        tiles: dict[Point, BlobLocation]
            The base-level tiles, keyed by (col, row) grid position.
        slidedat: Slidedat
            The slide's `Slidedat` (tile size, overlap, geometry).
        position_bytes: bytes | None
            The raw position-buffer blob, or None to use nominal overlap.
        """
        tile_size = slidedat.tile_size
        tile_width, tile_height = tile_size.width, tile_size.height
        divisions = slidedat.divisions
        photo_columns = slidedat.imagenumber_x // divisions
        photo_rows = slidedat.imagenumber_y // divisions
        photo_origins = self._decode_positions(slidedat, position_bytes)
        if photo_origins is None:
            photo_origins = self._nominal_photo_origins(slidedat)

        origins: dict[Point, tuple[int, int]] = {}
        for grid_position in tiles:
            grid_x, grid_y = grid_position.x, grid_position.y
            photo_x, photo_y = grid_x // divisions, grid_y // divisions
            # a row-major index past the photo grid would wrap to the next row
            photo = (
                photo_origins.get(photo_y * photo_columns + photo_x)
                if photo_x < photo_columns and photo_y < photo_rows
                else None
            )
            if photo is None:
                # every base-level tile seen so far has a recorded photo position
                raise NotImplementedError(
                    f"Base-level tile {(grid_x, grid_y)} has no recorded camera "
                    "position."
                )
            origins[grid_position] = (
                photo[0] + (grid_x % divisions) * tile_width,
                photo[1] + (grid_y % divisions) * tile_height,
            )
        if not origins:
            raise NotImplementedError("MIRAX slide without base-level tiles")
        origin_x = min(x for x, _ in origins.values())
        origin_y = min(y for _, y in origins.values())
        self._origin = Point(origin_x, origin_y)
        width = max(x for x, _ in origins.values()) - origin_x + tile_width
        height = max(y for _, y in origins.values()) - origin_y + tile_height
        whole_tile = Region(Point(0, 0), tile_size)
        self._overlap = TileOverlap(
            Size(width, height),
            {
                grid_position: [
                    TilePlacement(whole_tile, PointF(x - origin_x, y - origin_y))
                ]
                for grid_position, (x, y) in origins.items()
            },
        )

    @property
    def origin(self) -> Point:
        """Base-level position of the bounding box in the slide's scan coordinates."""
        return self._origin

    @property
    def dimensions(self) -> Size:
        """Size of the base level."""
        return self._overlap.image_size

    @property
    def overlap(self) -> TileOverlap:
        """Placement of the base-level tiles, keyed by (col, row) grid position."""
        return self._overlap

    @staticmethod
    def _nominal_photo_origins(slidedat: Slidedat) -> dict[int, tuple[int, int]]:
        """Camera-photo origins from the nominal per-photo overlap, for a slide
        without recorded positions.

        Photos step by their size less the overlap. The overlap may be fractional,
        so each origin is rounded on its own and rounding error can't accumulate
        across photo seams.

        Parameters
        ----------
        slidedat: Slidedat
            The slide's `Slidedat` (photo grid geometry, tile size, overlap).

        Returns
        -------
        dict[int, tuple[int, int]]
            {camera_index: (x, y)} for every photo of the grid, in row-major order.
        """
        divisions = slidedat.divisions
        columns = slidedat.imagenumber_x // divisions
        rows = slidedat.imagenumber_y // divisions
        step_x = divisions * slidedat.tile_size.width - slidedat.overlap.x
        step_y = divisions * slidedat.tile_size.height - slidedat.overlap.y
        return {
            photo_y * columns + photo_x: (
                round(photo_x * step_x),
                round(photo_y * step_y),
            )
            for photo_y in range(rows)
            for photo_x in range(columns)
        }

    @staticmethod
    def _decode_positions(
        slidedat: Slidedat, raw: bytes | None
    ) -> dict[int, tuple[int, int]] | None:
        """Decode recorded camera-photo origins.

        One entry per position in row-major order, each flag(1) + x(int32) +
        y(int32). v2.2+ stores the blob DEFLATE-compressed.

        Parameters
        ----------
        slidedat: Slidedat
            The slide's `Slidedat` (photo grid geometry).
        raw: bytes | None
            The raw position-buffer blob, or None.

        Returns
        -------
        dict[int, tuple[int, int]] | None
            {camera_index: (x, y)} for flagged positions, or None if there's no
            (readable) position buffer.
        """
        if raw is None:
            return None
        divisions = slidedat.divisions
        columns = slidedat.imagenumber_x // divisions
        rows = slidedat.imagenumber_y // divisions
        position_count = columns * rows
        if len(raw) < position_count * 9:  # v>=2.2 stores it DEFLATE-compressed
            import zlib

            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                return None
        positions: dict[int, tuple[int, int]] = {}
        for position_index in range(min(position_count, len(raw) // 9)):
            flag, pos_x, pos_y = struct.unpack_from("<Bii", raw, position_index * 9)
            if flag:
                positions[position_index] = (pos_x, pos_y)
        return positions
