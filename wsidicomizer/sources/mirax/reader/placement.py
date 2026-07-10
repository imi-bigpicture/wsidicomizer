"""Places MIRAX tiles in pixel space and answers spatial queries.

Uses the recorded VIMSLIDE_POSITION_BUFFER when present (absolute, jitter-free);
otherwise the nominal per-photo OVERLAP_X/Y from Slidedat. Pure computation — the
caller reads the position-buffer bytes and passes them in.
"""

import struct
from collections.abc import Iterator

from wsidicomizer.sources.mirax.reader.index import GridPos, Loc, MiraxIndex
from wsidicomizer.sources.mirax.reader.slidedat import Slidedat

Placed = tuple[int, int, Loc]  # (pixel x, pixel y, source tile) after placement


class TilePlacement:
    """Per-level tile pixel positions, level dimensions, and a spatial index.

    The origin (0,0) is the top-left of the scanned tissue bounding box, not the
    full glass slide.
    """

    def __init__(
        self, index: MiraxIndex, metadata: Slidedat, position_bytes: bytes | None
    ):
        """Compute tile positions and build the spatial index.

        Parameters
        ----------
        index: MiraxIndex
            The parsed Index.dat (per-level tile grids).
        metadata: Slidedat
            The slide's parsed Slidedat.ini (tile size, overlap, geometry).
        position_bytes: bytes | None
            The raw position-buffer blob, or None to use nominal overlap.
        """
        self._tile_width, self._tile_height = metadata.tile_size
        divisions = metadata.divisions
        photo_columns = metadata.imagenumber_x // divisions
        overlap_x, overlap_y = metadata.overlap
        tile_width, tile_height = self._tile_width, self._tile_height
        positions = self._decode_positions(metadata, position_bytes)

        def level0_origin(grid_x: int, grid_y: int) -> tuple[int, int]:
            if positions is not None:
                camera = (grid_y // divisions) * photo_columns + grid_x // divisions
                position = positions.get(camera)
                if position is not None:
                    return (
                        position[0] + (grid_x % divisions) * tile_width,
                        position[1] + (grid_y % divisions) * tile_height,
                    )
            return (
                round(grid_x * tile_width - (grid_x // divisions) * overlap_x),
                round(grid_y * tile_height - (grid_y // divisions) * overlap_y),
            )

        levels = index.levels
        # level-0 coords come straight from the grid keys (col == x at level 0)
        origins = {grid_pos: level0_origin(*grid_pos) for grid_pos in levels[0]}
        origin_x = min(x for x, _ in origins.values())
        origin_y = min(y for _, y in origins.values())
        width0 = max(x for x, _ in origins.values()) - origin_x + tile_width
        height0 = max(y for _, y in origins.values()) - origin_y + tile_height
        self.level_dimensions = [
            (-(-width0 // 2**level), -(-height0 // 2**level))
            for level in range(len(levels))
        ]

        # Per-level spatial index: bucket tiles into a tw*th grid over pixel space
        # so tiles_in touches O(tiles-in-window) instead of O(tiles-in-level). A
        # tile is inserted into every bucket it overlaps; querying the window's
        # buckets then catches every intersecting tile.
        self._grid: list[dict[GridPos, list[Placed]]] = []
        for level, tiles in enumerate(levels):
            grid: dict[GridPos, list[Placed]] = {}
            for (col, row), loc in tiles.items():
                base_x, base_y = level0_origin(col << level, row << level)
                tile_x = (base_x - origin_x) >> level
                tile_y = (base_y - origin_y) >> level
                placed = (tile_x, tile_y, loc)
                for bucket_x in range(
                    tile_x // tile_width, (tile_x + tile_width - 1) // tile_width + 1
                ):
                    for bucket_y in range(
                        tile_y // tile_height,
                        (tile_y + tile_height - 1) // tile_height + 1,
                    ):
                        grid.setdefault((bucket_x, bucket_y), []).append(placed)
            self._grid.append(grid)

    @staticmethod
    def _decode_positions(
        metadata: Slidedat, raw: bytes | None
    ) -> dict[int, tuple[int, int]] | None:
        """Decode recorded camera-photo origins.

        One entry per position in row-major order, each flag(1) + x(int32) +
        y(int32). v2.2+ stores the blob DEFLATE-compressed.

        Parameters
        ----------
        metadata: Slidedat
            The slide's parsed Slidedat.ini (photo grid geometry).
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
        divisions = metadata.divisions
        columns = metadata.imagenumber_x // divisions
        rows = metadata.imagenumber_y // divisions
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

    def tiles_in(
        self, level: int, left: int, top: int, width: int, height: int
    ) -> Iterator[Placed]:
        """Yield the source tiles overlapping a level window.

        Parameters
        ----------
        level: int
            Pyramid level to query.
        left: int
            Left edge of the window, in level pixels.
        top: int
            Top edge of the window, in level pixels.
        width: int
            Window width, in level pixels.
        height: int
            Window height, in level pixels.

        Yields
        ------
        Placed
            (tile_x, tile_y, loc) for each overlapping tile, each once.
        """
        tile_width, tile_height = self._tile_width, self._tile_height
        grid = self._grid[level]
        seen: set[Loc] = set()
        for bucket_x in range(left // tile_width, (left + width - 1) // tile_width + 1):
            for bucket_y in range(
                top // tile_height, (top + height - 1) // tile_height + 1
            ):
                for tile_x, tile_y, loc in grid.get((bucket_x, bucket_y), ()):
                    if loc in seen:
                        continue
                    seen.add(loc)
                    if (
                        tile_x + tile_width <= left
                        or tile_x >= left + width
                        or tile_y + tile_height <= top
                        or tile_y >= top + height
                    ):
                        continue
                    yield tile_x, tile_y, loc
