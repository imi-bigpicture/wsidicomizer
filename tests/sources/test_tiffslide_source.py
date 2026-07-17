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

import numpy as np
import pytest
import tifffile
from upath import UPath
from wsidicom.geometry import SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import Pyramid

from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.sources.tiffslide import TiffSlideSource


@pytest.fixture
def metadata() -> WsiDicomizerMetadata:
    return WsiDicomizerMetadata(
        pyramid=Pyramid(ImageMetadata(pixel_spacing=SizeMm(0.0005, 0.0005)), [])
    )


@pytest.fixture
def slide(testdata_dir: Path) -> Path:
    path = testdata_dir.joinpath("slides", "svs", "CMU-1", "CMU-1.svs")
    if not path.exists():
        pytest.skip("svs test data not available")
    return path


def _write_tiff(path: Path, array: np.ndarray) -> None:
    photometric = "minisblack" if array.ndim == 2 else "rgb"
    tifffile.imwrite(path, array, tile=(256, 256), photometric=photometric)


class TestTiffSlideSource:
    @pytest.mark.parametrize(
        ["array", "expected_samples", "expected_photometric"],
        [
            (np.zeros((512, 512), np.uint8), 1, "MONOCHROME2"),
            (np.zeros((512, 512, 3), np.uint8), 3, "YBR_FULL_422"),
        ],
    )
    def test_default_encoder_matches_pixel_format(
        self,
        tmp_path: Path,
        metadata: WsiDicomizerMetadata,
        array: np.ndarray,
        expected_samples: int,
        expected_photometric: str,
    ):
        # Arrange - no encoder supplied; the source must pick one matching the
        # file's pixel format. (A full convert isn't used here: tiffslide's
        # reader needs a real pyramidal structure that imwrite doesn't produce;
        # the level image data exercises the encoder selection on its own.)
        path = tmp_path / "image.tiff"
        _write_tiff(path, array)

        # Act
        source = TiffSlideSource(path, None, metadata=metadata)
        image_data = source._create_level_image_data(0)

        # Assert
        assert image_data.samples_per_pixel == expected_samples
        assert image_data.photometric_interpretation == expected_photometric
        source.close()

    def test_supports_local_path(self, slide: Path):
        # Act
        supported = TiffSlideSource.is_supported(slide)

        # Assert
        assert supported is True

    def test_supports_fsspec_path(self, slide: Path):
        # Act
        supported = TiffSlideSource.is_supported(UPath(slide.as_uri()))

        # Assert
        assert supported is True
