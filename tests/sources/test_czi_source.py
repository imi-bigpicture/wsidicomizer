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

from pathlib import Path

import pytest
from upath import UPath

from wsidicomizer.sources import CziSource


@pytest.fixture
def slide(testdata_dir: Path) -> Path:
    path = testdata_dir.joinpath("slides", "czi", "czi1", "input.czi")
    if not path.exists():
        pytest.skip("czi test data not available")
    return path


class TestCziSource:
    def test_supports_local_path(self, slide: Path):
        # Act
        supported = CziSource.is_supported(slide)

        # Assert
        assert supported is True

    def test_does_not_support_fsspec_path(self, slide: Path):
        # czifile reads only real local files, so the same slide must be declined
        # when given as a fsspec url (file://) it cannot consume.

        # Act
        supported = CziSource.is_supported(UPath(slide.as_uri()))

        # Assert
        assert supported is False
