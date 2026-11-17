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

"""Tests for the MIRAX reader itself (placement, tiles, channels)."""

from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent
from typing import Any, BinaryIO

import numpy as np
import pytest
from opentile.file import FileHandlePool

from wsidicomizer.sources.mirax.reader import (
    MiraxAssociatedImageType,
    MiraxReader,
    MrxsError,
    mirax_reader,
)
from wsidicomizer.sources.mirax.reader.decoder import MiraxJpegDecoder


def _write_slidedat(directory: Path, slidedat: str) -> Path:
    """Write a minimal slide, a .mrxs and its Slidedat.ini, and return its path."""
    path = directory / "slide.mrxs"
    path.touch()
    (directory / "slide").mkdir()
    (directory / "slide" / "Slidedat.ini").write_text(dedent(slidedat))
    return path


@pytest.fixture
def reader(mirax_path: Path) -> Iterator[MiraxReader]:
    slide = MiraxReader(mirax_path)
    yield slide
    slide.close()


class TestMiraxReader:
    def test_associated_image_sizes_match_slidedat(self, reader: MiraxReader):
        # Act
        associated = reader.associated_images

        # Assert - decoded sizes must match Slidedat.ini (nonhierarchical parsing)
        assert associated[MiraxAssociatedImageType.THUMBNAIL].size == (854, 1724)
        assert associated[MiraxAssociatedImageType.MACRO].size == (563, 1128)
        assert associated[MiraxAssociatedImageType.LABEL].size == (615, 462)

    def test_decodes_rgb_tiles(self, reader: MiraxReader):
        # Arrange
        grid_position = next(iter(reader.overlap.placements))

        # Act
        tile = reader.decode_tile(grid_position)

        # Assert
        assert tile.dtype == reader.dtype == np.uint8
        assert tile.shape == (
            reader.slidedat.tile_size.height,
            reader.slidedat.tile_size.width,
            3,
        )

    def test_brightfield_has_mpp_and_no_channels(self, reader: MiraxReader):
        # Act
        mpp = reader.slidedat.mpp

        # Assert
        assert mpp is not None and mpp[0] > 0 and mpp[1] > 0
        assert reader.channels == []

    def test_overlap_is_removed(self, reader: MiraxReader):
        # Arrange - a naive abutting layout ignores the per-photo overlap
        columns = {position.x for position in reader._index.tiles}
        abutting_width = (
            max(columns) - min(columns) + 1
        ) * reader.slidedat.tile_size.width

        # Act
        width = reader.dimensions.width

        # Assert
        assert reader._index.position_buffer is not None
        assert width < abutting_width

    def test_tile_of_other_bit_depth_is_refused(
        self, reader: MiraxReader, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange - the 8-bit JPEG tiles decode as 16-bit, as a slide whose stated
        # bit depth disagrees with its tiles would
        decode = MiraxJpegDecoder.decode

        def decode_16_bit(self: MiraxJpegDecoder, blob: bytes) -> np.ndarray:
            return decode(self, blob).astype(np.uint16)

        monkeypatch.setattr(MiraxJpegDecoder, "decode", decode_16_bit)

        # Act / Assert - refused instead of wrapped into an 8-bit canvas
        with pytest.raises(MrxsError, match="bit depth"):
            reader.decode_tile(next(iter(reader.overlap.placements)))

    def test_tile_smaller_than_tile_size_is_refused(
        self, reader: MiraxReader, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange - the JPEG tiles decode one row short of the slide's tile size
        decode = MiraxJpegDecoder.decode

        def decode_short(self: MiraxJpegDecoder, blob: bytes) -> np.ndarray:
            return decode(self, blob)[:-1]

        monkeypatch.setattr(MiraxJpegDecoder, "decode", decode_short)

        # Act / Assert - refused instead of failing to paste
        with pytest.raises(MrxsError, match="tile size"):
            reader.decode_tile(next(iter(reader.overlap.placements)))

    def test_rejects_reduced_pyramid(self, reduced_mirax_path: Path):
        # Act / Assert - a truncated pyramid is detected and rejected when opened
        with pytest.raises(NotImplementedError):
            MiraxReader(reduced_mirax_path)

    def test_rejects_multi_leaf_fluorescence_on_open(self, tmp_path: Path):
        # Arrange - 4 channels, so they span two data leaves
        path = _write_slidedat(
            tmp_path,
            """
            [GENERAL]
            SLIDE_TYPE = SLIDE_TYPE_FLUORESCENCE
            [HIERARCHICAL]
            HIER_1_NAME = Slide filter level
            HIER_1_COUNT = 4
            HIER_1_VAL_0_SECTION = C0
            HIER_1_VAL_1_SECTION = C1
            HIER_1_VAL_2_SECTION = C2
            HIER_1_VAL_3_SECTION = C3
            [C0]
            STORING_CHANNEL_NUMBER = 0
            DATA_IN_THIS_FILTER_LEVEL = LEAF_0
            [C1]
            STORING_CHANNEL_NUMBER = 1
            DATA_IN_THIS_FILTER_LEVEL = LEAF_0
            [C2]
            STORING_CHANNEL_NUMBER = 2
            DATA_IN_THIS_FILTER_LEVEL = LEAF_0
            [C3]
            STORING_CHANNEL_NUMBER = 0
            DATA_IN_THIS_FILTER_LEVEL = LEAF_1
            """,
        )

        # Act / Assert - refused when opened, not when a channel is first read
        with pytest.raises(NotImplementedError):
            MiraxReader(path)

    def test_failed_open_closes_data_files(
        self, mirax_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange - fail in placement, after the position buffer has been read
        # through a data file handle
        handles: list[BinaryIO] = []

        class RecordingPool(FileHandlePool):
            def open_or_wait(self) -> BinaryIO:
                handle = super().open_or_wait()
                handles.append(handle)
                return handle

        def failing_layout(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("placement failed")

        monkeypatch.setattr(mirax_reader, "FileHandlePool", RecordingPool)
        monkeypatch.setattr(mirax_reader, "MiraxTileLayout", failing_layout)

        # Act
        with pytest.raises(RuntimeError):
            MiraxReader(mirax_path)

        # Assert
        assert handles
        assert all(handle.closed for handle in handles)
