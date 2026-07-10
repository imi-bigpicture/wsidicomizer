"""Binary parsing of the MIRAX Index.dat file.

Index.dat is a 5-char version, a 32-char slide id, then two root pointers into a
tree of unaligned little-endian int32s. Each record points at a linked list of
data pages ([count][next_ptr][count * entry]); the first page always has count 0.
"""

import struct
from math import gcd

from wsidicomizer.sources.mirax.reader.slidedat import Slidedat

Loc = tuple[int, int, int]  # (file number, byte offset, length) of a stored blob
GridPos = tuple[int, int]  # (column, row) on a level's tile grid


class MiraxIndex:
    """Parsed Index.dat: per-level tile locations, associated-image locations, and
    the position-buffer location — all as `Loc` (file, offset, length) into the
    Data*.dat files."""

    # Nonhierarchical group holding the tile position buffer:
    # VIMSLIDE_POSITION_BUFFER on older slides, StitchingIntensityLayer on newer
    # (2.2+) ones (DEFLATE-compressed). The two are era-specific, they don't coexist.
    _POSITION_GROUPS = ("VIMSLIDE_POSITION_BUFFER", "StitchingIntensityLayer")

    def __init__(self, index_bytes: bytes, metadata: Slidedat):
        """Parse an Index.dat.

        Parameters
        ----------
        index_bytes: bytes
            The raw Index.dat contents.
        metadata: Slidedat
            The slide's parsed Slidedat.ini, for grid geometry and the
            nonhierarchical entry order.
        """
        hier_root = self._read_u32(index_bytes, 37)
        nonhier_root = self._read_u32(index_bytes, 41)
        imagenumber_x = metadata.imagenumber_x

        # Hierarchical: one root pointer per HIER_x_VAL. Only HIER_0 (the zoom
        # pyramid) carries tiles; its VAL i is level i. A tile's grid position is
        # recovered from its index (y * IMAGENUMBER_X + x) and shifted down to the
        # level's own grid.
        raw_levels = [
            self._follow_pages(
                index_bytes, self._read_u32(index_bytes, hier_root + level * 4), 4
            )
            for level in range(metadata.level_count)
        ]

        # A truncated pyramid (bottom N levels dropped, e.g. a reduced re-export)
        # keeps the original IMAGENUMBER, so the finest level's coordinates are
        # multiples of 2**N instead of consecutive. Detect N from their gcd so the
        # grid normalizes to (col, row); native slides give N == 0 (gcd is odd).
        coord_gcd = 0
        for tile_index, *_ in raw_levels[0]:
            coord_gcd = gcd(
                coord_gcd, tile_index % imagenumber_x, tile_index // imagenumber_x
            )
        low_bit = coord_gcd & -coord_gcd  # lowest set bit == 2**base_shift
        self.base_shift = low_bit.bit_length() - 1 if coord_gcd else 0

        self.levels: list[dict[GridPos, Loc]] = []
        for level, entries in enumerate(raw_levels):
            shift = self.base_shift + level
            tiles: dict[GridPos, Loc] = {}
            for tile_index, offset, length, file_number in entries:
                tile_x = tile_index % imagenumber_x
                tile_y = tile_index // imagenumber_x
                grid_pos = (tile_x >> shift, tile_y >> shift)
                tiles[grid_pos] = (file_number, offset, length)
            self.levels.append(tiles)

        # Nonhierarchical: associated images + the position buffer (see
        # _POSITION_GROUPS). Entry layout is [0, 0, offset, length, file_number].
        # The position buffer's value name isn't unique, so it's found by group.
        self.nonhier: dict[str, Loc] = {}
        self.position_buffer: Loc | None = None
        for flat_index, (group_name, value_name) in enumerate(
            metadata.nonhier_entries()
        ):
            first_page = self._read_u32(index_bytes, nonhier_root + flat_index * 4)
            entries = self._follow_pages(index_bytes, first_page, 5)
            if not entries:
                continue
            _, _, offset, length, file_number = entries[0]
            loc = (file_number, offset, length)
            self.nonhier[value_name] = loc
            if group_name in self._POSITION_GROUPS and self.position_buffer is None:
                self.position_buffer = loc

    @staticmethod
    def _read_u32(buffer: bytes, offset: int) -> int:
        """Read a little-endian uint32.

        Parameters
        ----------
        buffer: bytes
            Buffer to read from.
        offset: int
            Byte offset to read at.

        Returns
        -------
        int
            The decoded uint32.
        """
        return struct.unpack_from("<I", buffer, offset)[0]

    @staticmethod
    def _follow_pages(
        index_bytes: bytes, first_page_ptr: int, ints_per_entry: int
    ) -> list[tuple[int, ...]]:
        """Walk a page linked list, returning every entry.

        Each page is [count][next_ptr][count * entry].

        Parameters
        ----------
        index_bytes: bytes
            The raw Index.dat contents.
        first_page_ptr: int
            Byte offset of the first page in the list.
        ints_per_entry: int
            Number of int32s per entry.

        Returns
        -------
        list[tuple[int, ...]]
            Every entry, each as a tuple of `ints_per_entry` int32s.
        """
        entries: list[tuple[int, ...]] = []
        page_ptr = first_page_ptr
        entry_format = "<" + "I" * ints_per_entry
        entry_step = ints_per_entry * 4
        while page_ptr:
            count = MiraxIndex._read_u32(index_bytes, page_ptr)
            next_ptr = MiraxIndex._read_u32(index_bytes, page_ptr + 4)
            base = page_ptr + 8
            for entry_index in range(count):
                offset = base + entry_index * entry_step
                entries.append(struct.unpack_from(entry_format, index_bytes, offset))
            page_ptr = next_ptr
        return entries
