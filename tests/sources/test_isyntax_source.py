from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from isyntax import ISyntax

from tests.conftest import test_parameters
from wsidicomizer.extras.isyntax.isyntax_metadata import ISyntaxMetadata


class TestIsyntaxSource:
    @pytest.mark.parametrize(
        "isyntax_test_data", [data for data in test_parameters["isyntax"].items()]
    )
    def test_metadata_read_label(
        self, testdata_dir: Path, isyntax_test_data: Tuple[str, Dict[str, Any]]
    ):
        # Arrange
        file_path = testdata_dir.joinpath("slides", "isyntax", isyntax_test_data[0])
        slide = ISyntax.open(file_path)
        metadata = ISyntaxMetadata(slide)

        # Act
        label = metadata.label

        # Assert
        assert label.barcode == "             "
