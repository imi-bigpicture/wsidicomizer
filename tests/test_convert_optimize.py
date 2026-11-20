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

"""Integration tests for converting with optimized JPEG Huffman tables."""

from pathlib import Path

import numpy as np
import pytest
from pydicom.uid import JPEG2000, JPEGBaseline8Bit
from upath import UPath
from wsidicom import WsiDicom, WsiFile, WsiLevelFile
from wsidicom.codec import JpegSettings

from wsidicomizer.wsidicomizer import WsiDicomizer


@pytest.mark.integrationtest
class TestConvertOptimize:
    @staticmethod
    def level_files_size(created_files: dict[UPath, WsiFile]) -> int:
        """Return the summed size of the created files of pyramid levels."""
        return sum(
            path.stat().st_size
            for path, created_file in created_files.items()
            if isinstance(created_file, WsiLevelFile)
        )

    @pytest.mark.parametrize(
        ["file_format", "file"], [("svs", "CMU-1/CMU-1.svs")], scope="module"
    )
    def test_optimize_recodes_passed_through_jpeg_tiles(
        self, wsi_file: Path, tmp_path: Path
    ):
        # Arrange
        plain_path = tmp_path.joinpath("plain")
        optimized_path = tmp_path.joinpath("optimized")
        plain_files = WsiDicomizer.convert(
            wsi_file, plain_path, include_levels=[-1], encoding=JpegSettings()
        )

        # Act
        optimized_files = WsiDicomizer.convert(
            wsi_file,
            optimized_path,
            include_levels=[-1],
            encoding=JpegSettings(optimize=True),
        )

        # Assert
        assert self.level_files_size(optimized_files) < self.level_files_size(
            plain_files
        )
        with (
            WsiDicom.open(plain_path) as plain_wsi,
            WsiDicom.open(optimized_path) as optimized_wsi,
        ):
            optimized_level = optimized_wsi.levels.base_level
            assert (
                optimized_level.default_instance.image_data.transfer_syntax
                == JPEGBaseline8Bit
            )
            assert np.array_equal(
                np.asarray(optimized_wsi.read_tile(optimized_level.level, (0, 0))),
                np.asarray(plain_wsi.read_tile(optimized_level.level, (0, 0))),
            )

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [("svs", "JP2K-33003-1/JP2K-33003-1.svs")],
        scope="module",
    )
    def test_optimize_passes_through_jpeg_2000_tiles(
        self, wsi_file: Path, tmp_path: Path
    ):
        # Arrange

        # Act
        WsiDicomizer.convert(
            wsi_file,
            tmp_path,
            include_levels=[-1],
            encoding=JpegSettings(optimize=True),
        )

        # Assert
        with WsiDicom.open(tmp_path) as wsi:
            image_data = wsi.levels.base_level.default_instance.image_data
            assert image_data.transfer_syntax == JPEG2000
