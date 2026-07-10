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

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from wsidicom.geometry import Point

from wsidicomizer.sources.mirax import MiraxSource


@pytest.fixture
def source(mirax_path: Path) -> Iterator[MiraxSource]:
    mirax_source = MiraxSource(mirax_path, None)
    yield mirax_source
    mirax_source.close()


@pytest.fixture
def fluorescence_source(fluorescence_mirax_path: Path) -> Iterator[MiraxSource]:
    mirax_source = MiraxSource(fluorescence_mirax_path, None)
    yield mirax_source
    mirax_source.close()


class TestMiraxSource:
    def test_is_supported(self, mirax_path: Path):
        # Act / Assert
        assert MiraxSource.is_supported(mirax_path)
        assert not MiraxSource.is_supported(mirax_path.with_suffix(".svs"))

    def test_reduced_pyramid_rejected_on_open(self, reduced_mirax_path: Path):
        # Assert - detection is lightweight, so a reduced pyramid passes
        # is_supported but is rejected when the reader is opened
        assert MiraxSource.is_supported(reduced_mirax_path)
        with pytest.raises(NotImplementedError):
            MiraxSource(reduced_mirax_path, None)

    def test_metadata(self, source: MiraxSource):
        # Act
        metadata = source.base_metadata
        image = metadata.pyramid.image

        # Assert
        assert image.pixel_spacing is not None
        assert image.image_coordinate_system is not None
        assert image.image_coordinate_system.rotation == 270.0  # WsiFormat.MIRAX
        # MIRAX-specific fields the openslide property model doesn't carry
        assert metadata.equipment.manufacturer == "3DHISTECH"
        assert metadata.equipment.software_versions is not None
        assert image.acquisition_datetime is not None

    def test_level_image_data_reads_rgb_tile(self, source: MiraxSource):
        # Arrange
        image_data = source._create_level_image_data(0)

        # Act
        tile = np.asarray(image_data.get_decoded_tile(Point(30, 79), 0.0, "1"))

        # Assert
        assert image_data.samples_per_pixel == 3
        assert tile.shape == (
            image_data.tile_size.height,
            image_data.tile_size.width,
            3,
        )

    def test_fluorescence_channels_as_grayscale_optical_paths(
        self, fluorescence_source: MiraxSource
    ):
        # Act
        image_data = fluorescence_source._create_level_image_data(3)
        optical_paths = fluorescence_source.base_metadata.pyramid.optical_paths
        path = image_data.optical_paths[0]
        tile = image_data.get_decoded_tile(Point(0, 0), 0.0, path)

        # Assert - each channel is its own grayscale MONOCHROME2 optical path
        assert image_data.samples_per_pixel == 1
        assert image_data.photometric_interpretation == "MONOCHROME2"
        assert len(image_data.optical_paths) == 3
        assert [op.identifier for op in optical_paths] == image_data.optical_paths
        assert tile.mode == "L"

    def test_png_fluorescence_channels(self, png_fluorescence_mirax_path: Path):
        # Arrange
        source = MiraxSource(png_fluorescence_mirax_path, None)

        # Act
        image_data = source._create_level_image_data(3)
        path = image_data.optical_paths[0]
        tile = image_data.get_decoded_tile(Point(0, 0), 0.0, path)

        # Assert - 8-bit PNG tiles split into grayscale channels
        assert image_data.bits == 8
        assert image_data.samples_per_pixel == 1
        assert len(image_data.optical_paths) == 3
        assert tile.mode == "L"
        source.close()

    def test_16bit_fluorescence_channels(self, high_bit_fluorescence_mirax_path: Path):
        # Arrange
        source = MiraxSource(high_bit_fluorescence_mirax_path, None)

        # Act
        image_data = source._create_level_image_data(3)
        path = image_data.optical_paths[0]
        tile = image_data.get_decoded_tile(Point(0, 0), 0.0, path)
        encoded = image_data.get_encoded_tile(Point(0, 0), 0.0, path)

        # Assert - 16-bit JPEG-XR tiles split into 16-bit MONOCHROME2 channels
        assert image_data.bits == 16
        assert image_data.samples_per_pixel == 1
        assert image_data.photometric_interpretation == "MONOCHROME2"
        assert tile.mode == "I;16"
        assert len(encoded) > 0
        source.close()
