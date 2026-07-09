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

"""Native transfer syntax passthrough for OpenTile native-tile sources."""

from pathlib import Path

import pytest
from pydicom.uid import UID
from wsidicom import WsiDicom

from wsidicomizer.wsidicomizer import WsiDicomizer

from .conftest import test_parameters


@pytest.mark.integrationtest
class TestNativePassthrough:
    @pytest.mark.parametrize(
        ["file_format", "file", "expected_transfer_syntax", "photometric"],
        [
            (
                file_format,
                file,
                file_parameters["transfer_syntax"],
                file_parameters["photometric_interpretation"],
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            if file_parameters.get("passthrough")
        ],
    )
    def test_native_passthrough_transfer_syntax(
        self,
        file_format: str,
        file: str,
        expected_transfer_syntax: UID,
        photometric: str,
        wsi_files: dict[str, dict[str, Path]],
    ):
        # Arrange
        file_path = wsi_files[file_format][file]
        if not file_path.exists():
            pytest.skip(f"{file_path} not present")

        # Act
        with WsiDicomizer.open(file_path) as wsi:
            assert isinstance(wsi, WsiDicom)
            image_data = wsi.pyramids[0].base_level.default_instance.image_data

            # Assert
            assert image_data.transfer_syntax == expected_transfer_syntax
            assert image_data.photometric_interpretation == photometric
