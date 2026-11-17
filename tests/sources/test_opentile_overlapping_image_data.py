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
from upath import UPath
from wsidicom.codec import Encoder
from wsidicom.codec.settings import JpegSettings
from wsidicom.geometry import Point

from wsidicomizer.errors import SourceNotSupportedError
from wsidicomizer.sources import OpenTileSource
from wsidicomizer.sources.opentile import opentile_source
from wsidicomizer.sources.opentile.opentile_image_data import (
    OpenTileLevelImageData,
    OpenTileOverlappingLevelImageData,
)


def slide_path(testdata_dir: Path, folders: tuple[str, ...], file: str) -> Path:
    for folder in folders:
        path = testdata_dir.joinpath("slides", folder, file)
        if path.exists():
            return path
    pytest.skip(f"{file} test data not available")


@pytest.fixture(scope="module")
def trestle_source(testdata_dir: Path) -> Iterator[OpenTileSource]:
    path = slide_path(testdata_dir, ("trestle", "trestle_tiff"), "CMU-1/CMU-1.tif")
    source = OpenTileSource(
        UPath(path), Encoder.create_for_settings(JpegSettings()), tile_size=512
    )
    yield source
    source.close()


@pytest.fixture(scope="module")
def ventana_path(testdata_dir: Path) -> Path:
    return slide_path(testdata_dir, ("ventana", "ventana_bif"), "OS-1/OS-1.bif")


@pytest.fixture(scope="module")
def ventana_source(ventana_path: Path) -> Iterator[OpenTileSource]:
    source = OpenTileSource(
        UPath(ventana_path), Encoder.create_for_settings(JpegSettings()), tile_size=512
    )
    yield source
    source.close()


class TestTrestleLevels:
    def test_base_level_is_plain_and_passed_through(
        self, trestle_source: OpenTileSource
    ):
        # Arrange - opentile re-grids Trestle's overlapping base level losslessly
        if trestle_source._tiler.levels[0].overlap is not None:
            pytest.skip("this opentile does not re-grid Trestle levels")

        # Act
        image_data = trestle_source._create_level_image_data(0)

        # Assert - an ordinary level whose tiles pass through without transcoding
        assert isinstance(image_data, OpenTileLevelImageData)
        assert not isinstance(image_data, OpenTileOverlappingLevelImageData)
        assert image_data.transcoder is None

    def test_only_base_level_is_read(self, trestle_source: OpenTileSource):
        # Arrange - the stored levels above the base are softer, shrunk or cropped

        # Act
        read_levels = sorted(trestle_source.pyramid_levels.values())

        # Assert - they are rebuilt from the base instead
        assert read_levels == [0]


class TestVentanaLevels:
    def test_only_base_levels_are_read(self, ventana_source: OpenTileSource):
        # Arrange - every Ventana level overlaps; above the base at fractional
        # positions
        tiler_levels = ventana_source._tiler.levels

        # Act
        read_levels = ventana_source.pyramid_levels.values()

        # Assert
        assert {tiler_levels[index].pyramid_index for index in read_levels} == {
            tiler_levels[0].pyramid_index
        }

    def test_tissue_tile_is_composed(self, ventana_source: OpenTileSource):
        # Arrange
        image_data = ventana_source._create_level_image_data(0)
        assert isinstance(image_data, OpenTileOverlappingLevelImageData)
        center = Point(
            image_data.tiled_size.width // 2, image_data.tiled_size.height // 2
        )

        # Act
        tile = image_data.get_decoded_tile(
            center, image_data.focal_planes[0], image_data.optical_paths[0]
        )

        # Assert - composed at the output tile size, with tissue in it
        assert tile.shape[:2] == (512, 512)
        assert (tile.mean(axis=2) < 200).mean() > 0.1

    def test_uncovered_tile_reuses_one_encoded_blank(
        self, ventana_source: OpenTileSource
    ):
        # Arrange - a tile far outside every placed piece
        image_data = ventana_source._create_level_image_data(0)
        assert isinstance(image_data, OpenTileOverlappingLevelImageData)
        outside = Point(image_data.tiled_size.width + 5, 0)

        # Act
        first = image_data.get_encoded_tile(
            outside, image_data.focal_planes[0], image_data.optical_paths[0]
        )
        second = image_data.get_encoded_tile(
            outside, image_data.focal_planes[0], image_data.optical_paths[0]
        )

        # Assert
        assert first is second
        decoded = image_data.get_decoded_tile(
            outside, image_data.focal_planes[0], image_data.optical_paths[0]
        )
        assert np.all(decoded == decoded.flat[0])


def test_file_opentile_fails_to_open_is_refused(
    ventana_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange - a file whose format is detected but that fails to open
    def fail(*args, **kwargs):
        raise ValueError("broken file")

    monkeypatch.setattr(opentile_source.OpenTile, "open", fail)

    # Act / Assert - refused, so another source is tried instead
    with pytest.raises(SourceNotSupportedError):
        OpenTileSource(UPath(ventana_path), None)
