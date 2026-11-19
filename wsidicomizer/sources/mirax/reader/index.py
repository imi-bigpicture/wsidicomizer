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

"""Binary parsing of the MIRAX Index.dat file.

Index.dat is a 5-char version, a 32-char slide id, then two root pointers into a
tree of unaligned little-endian int32s. Each record points at a linked list of
data pages ([count][next page pointer][count * entry]); the first page always has
count 0.
"""

import struct
from dataclasses import dataclass
from math import gcd

from opentile.geometry import Point

from wsidicomizer.sources.mirax.reader.slidedat import Slidedat

# Index.dat layout
_INT_SIZE = 4
"""Bytes per little-endian int32, the unit everything in the file is made of."""
_VERSION_LENGTH = 5
"""Bytes of the version string the file starts with."""
_SLIDE_ID_LENGTH = 32
"""Bytes of the slide id that follows the version."""
_HIERARCHICAL_ROOT_OFFSET = _VERSION_LENGTH + _SLIDE_ID_LENGTH
"""Offset of the pointer to the hierarchical records, one per HIER_x_VAL."""
_NONHIERARCHICAL_ROOT_OFFSET = _HIERARCHICAL_ROOT_OFFSET + _INT_SIZE
"""Offset of the pointer to the nonhierarchical records, one per entry."""
_PAGE_HEADER_SIZE = 2 * _INT_SIZE
"""Bytes of a data page's [count][next page pointer] header."""
_TILE_ENTRY_INTS = 4
"""Int32s per tile entry: [tile index, offset, length, file number]."""
_NONHIERARCHICAL_ENTRY_INTS = 5
"""Int32s per nonhierarchical entry: [0, 0, offset, length, file number]."""


@dataclass(frozen=True, slots=True)
class BlobLocation:
    """Where a stored blob lives in the Data*.dat files."""

    file_number: int
    """Index of the Data*.dat file."""
    offset: int
    """Byte offset of the blob in the file."""
    length: int
    """Length of the blob in bytes."""


class MiraxIndex:
    """Parsed Index.dat: base-level tile locations, associated-image locations, and
    the position-buffer location — all as `BlobLocation`s into the Data*.dat files.

    The stored lower-resolution levels are not parsed: they are mosaics of camera
    photos at fractional positions, so the pyramid is rebuilt from the base level.
    """

    # Nonhierarchical group holding the tile position buffer:
    # VIMSLIDE_POSITION_BUFFER on older slides, StitchingIntensityLayer on newer
    # (2.2+) ones (DEFLATE-compressed). The two are era-specific; a slide with
    # more than one is refused.
    _POSITION_GROUPS = ("VIMSLIDE_POSITION_BUFFER", "StitchingIntensityLayer")

    def __init__(self, index_bytes: bytes, slidedat: Slidedat):
        """Parse an Index.dat.

        Parameters
        ----------
        index_bytes: bytes
            The raw Index.dat contents.
        slidedat: Slidedat
            The slide's `Slidedat`, for grid geometry and the
            nonhierarchical entry order.
        """
        hierarchical_root = self._read_uint32(index_bytes, _HIERARCHICAL_ROOT_OFFSET)
        nonhierarchical_root = self._read_uint32(
            index_bytes, _NONHIERARCHICAL_ROOT_OFFSET
        )
        imagenumber_x = slidedat.imagenumber_x

        # Hierarchical: one root pointer per HIER_x_VAL. Only HIER_0 (the zoom
        # pyramid) carries tiles, and its VAL 0, the first pointer, is the base
        # level. A tile's grid position is recovered from its index
        # (y * IMAGENUMBER_X + x).
        entries = self._follow_pages(
            index_bytes,
            self._read_uint32(index_bytes, hierarchical_root),
            _TILE_ENTRY_INTS,
        )

        # A truncated pyramid (bottom N levels dropped, e.g. a reduced re-export)
        # keeps the original IMAGENUMBER, so the finest level's coordinates are
        # multiples of 2**N instead of consecutive. Detect N from their greatest
        # common divisor so the grid normalizes to (col, row); native slides give
        # N == 0 (the divisor is odd).
        common_divisor = 0
        for tile_index, *_ in entries:
            common_divisor = gcd(
                common_divisor, tile_index % imagenumber_x, tile_index // imagenumber_x
            )
        # its lowest set bit is the largest power of two dividing it: 2**base_shift
        power_of_two_divisor = common_divisor & -common_divisor
        self._base_shift = (
            power_of_two_divisor.bit_length() - 1 if common_divisor else 0
        )

        self._tiles: dict[Point, BlobLocation] = {}
        for tile_index, offset, length, file_number in entries:
            tile_x = tile_index % imagenumber_x
            tile_y = tile_index // imagenumber_x
            grid_position = Point(
                tile_x >> self._base_shift, tile_y >> self._base_shift
            )
            self._tiles[grid_position] = BlobLocation(file_number, offset, length)

        # Nonhierarchical: associated images + the position buffer (see
        # _POSITION_GROUPS). The position buffer's value name isn't unique, so
        # it's found by group.
        self._nonhierarchical: dict[str, BlobLocation] = {}
        self._position_buffer: BlobLocation | None = None
        for flat_index, (group_name, value_name) in enumerate(
            slidedat.nonhierarchical_entries()
        ):
            first_page = self._read_uint32(
                index_bytes, nonhierarchical_root + flat_index * _INT_SIZE
            )
            entries = self._follow_pages(
                index_bytes, first_page, _NONHIERARCHICAL_ENTRY_INTS
            )
            if not entries:
                continue
            _, _, offset, length, file_number = entries[0]
            location = BlobLocation(file_number, offset, length)
            self._nonhierarchical[value_name] = location
            if group_name in self._POSITION_GROUPS:
                if self._position_buffer is not None:
                    raise NotImplementedError(
                        "MIRAX slide with more than one tile position buffer; "
                        "which one places the tiles is unknown"
                    )
                self._position_buffer = location

    @property
    def base_shift(self) -> int:
        """N for a truncated pyramid whose finest level is 2**N-spaced on the
        original grid; 0 for a native-resolution slide."""
        return self._base_shift

    @property
    def tiles(self) -> dict[Point, BlobLocation]:
        """Location of each base-level tile, by (col, row) grid position."""
        return self._tiles

    @property
    def nonhierarchical(self) -> dict[str, BlobLocation]:
        """Location of each nonhierarchical entry (associated images, position
        buffer), by value name."""
        return self._nonhierarchical

    @property
    def position_buffer(self) -> BlobLocation | None:
        """Location of the tile position buffer, or None if the slide has none."""
        return self._position_buffer

    @staticmethod
    def _read_uint32(buffer: bytes, offset: int) -> int:
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

    @classmethod
    def _follow_pages(
        cls, index_bytes: bytes, first_page_pointer: int, ints_per_entry: int
    ) -> list[tuple[int, ...]]:
        """Walk a page linked list, returning every entry.

        Each page is [count][next page pointer][count * entry].

        Parameters
        ----------
        index_bytes: bytes
            The raw Index.dat contents.
        first_page_pointer: int
            Byte offset of the first page in the list.
        ints_per_entry: int
            Number of int32s per entry.

        Returns
        -------
        list[tuple[int, ...]]
            Every entry, each as a tuple of `ints_per_entry` int32s.
        """
        entries: list[tuple[int, ...]] = []
        page_pointer = first_page_pointer
        entry_format = "<" + "I" * ints_per_entry
        entry_size = ints_per_entry * _INT_SIZE
        while page_pointer:
            count = cls._read_uint32(index_bytes, page_pointer)
            next_page_pointer = cls._read_uint32(index_bytes, page_pointer + _INT_SIZE)
            first_entry = page_pointer + _PAGE_HEADER_SIZE
            for entry_index in range(count):
                offset = first_entry + entry_index * entry_size
                entries.append(struct.unpack_from(entry_format, index_bytes, offset))
            page_pointer = next_page_pointer
        return entries
