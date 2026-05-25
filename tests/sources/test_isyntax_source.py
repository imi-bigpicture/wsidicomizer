#    Copyright 2025 SECTRA AB
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

from pathlib import Path
from typing import Any

import pytest
from isyntax import ISyntax

from tests.conftest import test_parameters
from wsidicomizer.extras.isyntax.isyntax_metadata import ISyntaxMetadata


class TestIsyntaxSource:
    @pytest.mark.parametrize(
        "isyntax_test_data", [data for data in test_parameters["isyntax"].items()]
    )
    def test_metadata_read_label(
        self, testdata_dir: Path, isyntax_test_data: tuple[str, dict[str, Any]]
    ):
        # Arrange
        file_path = testdata_dir.joinpath("slides", "isyntax", isyntax_test_data[0])
        slide = ISyntax.open(file_path)
        metadata = ISyntaxMetadata(slide)

        # Act
        label = metadata.label

        # Assert
        assert label.barcode == "             "
