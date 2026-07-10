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


@pytest.fixture
def mirax_path(testdata_dir: Path) -> Path:
    path = testdata_dir / "slides" / "mirax" / "CMU-1" / "CMU-1.mrxs"
    if not path.is_file():
        pytest.skip(f"missing test slide {path}")
    return path


@pytest.fixture
def reduced_mirax_path(testdata_dir: Path) -> Path:
    # a reduced re-export (bottom pyramid levels dropped) - not supported
    path = testdata_dir / "slides" / "mirax" / "CMU-1-Saved-1_16.mrxs"
    if not path.is_file():
        pytest.skip(f"missing reduced test slide {path}")
    return path


@pytest.fixture
def fluorescence_mirax_path(testdata_dir: Path) -> Path:
    path = (
        testdata_dir
        / "slides"
        / "mirax"
        / "Mirax2-Fluorescence-1"
        / "Mirax2-Fluorescence-1.mrxs"
    )
    if not path.is_file():
        pytest.skip(f"missing fluorescence test slide {path}")
    return path


@pytest.fixture
def png_fluorescence_mirax_path(testdata_dir: Path) -> Path:
    # an 8-bit PNG-tiled fluorescence slide
    path = testdata_dir / "slides" / "mirax" / "Liver_v1" / "Liver_v1.mrxs"
    if not path.is_file():
        pytest.skip(f"missing PNG fluorescence test slide {path}")
    return path


@pytest.fixture
def high_bit_fluorescence_mirax_path(testdata_dir: Path) -> Path:
    # a 16-bit JPEG-XR fluorescence slide
    path = testdata_dir / "slides" / "mirax" / "CK1" / "CK1.mrxs"
    if not path.is_file():
        pytest.skip(f"missing 16-bit fluorescence test slide {path}")
    return path
