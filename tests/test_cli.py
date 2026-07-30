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

import pytest
from click.testing import CliRunner

from wsidicomizer.cli import main


@pytest.mark.unittest
class TestCli:
    def test_missing_input_gives_error(self, tmp_path):
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(main, ["-i", str(tmp_path.joinpath("missing.svs"))])

        # Assert
        assert result.exit_code == 2
        assert "does not exist" in result.output

    @pytest.mark.parametrize("options", ["not json", '["not", "an", "object"]'])
    def test_file_options_that_are_not_a_json_object_gives_error(
        self, tmp_path, options: str
    ):
        # Arrange
        runner = CliRunner()
        input_path = tmp_path.joinpath("input.svs")
        input_path.touch()

        # Act
        result = runner.invoke(main, ["-i", str(input_path), "--file-options", options])

        # Assert
        assert result.exit_code == 2
        assert "--file-options" in result.output
