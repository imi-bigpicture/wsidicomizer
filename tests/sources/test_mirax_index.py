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

"""Tests for parsing the MIRAX Index.dat (synthetic index, no slide needed)."""

import struct
from types import SimpleNamespace
from typing import Any, cast

import pytest

from wsidicomizer.sources.mirax.reader.index import BlobLocation, MiraxIndex


@pytest.mark.unittest
class TestMiraxIndex:
    @staticmethod
    def build_index(
        entries: list[tuple[str, str]],
    ) -> tuple[bytes, Any]:
        """An Index.dat with no tiles and one stored blob per nonhierarchical
        entry, the n-th at offset 100 * n in data file n, and a Slidedat stand-in
        listing the entries."""
        header = bytes(37)  # version + slide id
        hierarchical_root = 45
        nonhierarchical_root = 49
        pages_start = nonhierarchical_root + 4 * len(entries)
        page_size = 8 + 5 * 4  # [count][next page pointer] + one 5-int entry
        records = struct.pack(
            "<III",
            hierarchical_root,
            nonhierarchical_root,
            0,  # HIER_0_VAL_0: no tile pages
        )
        records += b"".join(
            struct.pack("<I", pages_start + index * page_size)
            for index in range(len(entries))
        )
        pages = b"".join(
            struct.pack("<IIIIIII", 1, 0, 0, 0, 100 * index, 10, index)
            for index in range(len(entries))
        )
        slidedat = SimpleNamespace(
            imagenumber_x=1, nonhierarchical_entries=lambda: entries
        )
        return header + records + pages, cast(Any, slidedat)

    def test_position_buffer_is_found_by_group(self):
        # Arrange
        index_bytes, slidedat = self.build_index(
            [
                ("VIMSLIDE_SLIDE_BARCODE", "ScanDataLayer_SlideBarcode"),
                ("VIMSLIDE_POSITION_BUFFER", "default"),
            ]
        )

        # Act
        index = MiraxIndex(index_bytes, slidedat)

        # Assert
        assert index.position_buffer == BlobLocation(1, 100, 10)
        assert index.nonhierarchical["ScanDataLayer_SlideBarcode"] == (
            BlobLocation(0, 0, 10)
        )

    def test_more_than_one_position_buffer_is_refused(self):
        # Arrange
        index_bytes, slidedat = self.build_index(
            [
                ("VIMSLIDE_POSITION_BUFFER", "default"),
                ("StitchingIntensityLayer", "StitchingIntensityLevel"),
            ]
        )

        # Act / Assert
        with pytest.raises(NotImplementedError):
            MiraxIndex(index_bytes, slidedat)
