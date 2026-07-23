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

import pytest
from wsidicom.geometry import PointMm
from wsidicom.metadata import ImageCoordinateSystem, ImageType

from wsidicomizer.sources.openslide_like.openslide_like_metadata import (
    OpenSlideLikeProperties,
)
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat

# Rotations that ImageCoordinateSystem.default_for accepts.
SUPPORTED_ROTATIONS = (0, 90, 180, 270)


class TestVendorToWsiFormat:
    @pytest.mark.parametrize(
        ["vendor", "expected"],
        [
            ("aperio", WsiFormat.SVS),
            ("Aperio", WsiFormat.SVS),  # case-insensitive
            ("hamamatsu", WsiFormat.NDPI),
            ("mirax", WsiFormat.MIRAX),
            ("ventana", WsiFormat.VENTANA),
            ("philips", WsiFormat.PHILIPS_TIFF),
            ("leica", None),  # not mapped to a WsiFormat
            ("not-a-vendor", None),
        ],
    )
    def test_wsi_format_from_vendor(self, vendor: str, expected: WsiFormat | None):
        # Arrange
        properties = OpenSlideLikeProperties(vendor=vendor)

        # Act
        result = properties.wsi_format

        # Assert
        assert result == expected

    def test_wsi_format_no_vendor(self):
        # Arrange
        properties = OpenSlideLikeProperties(vendor=None)

        # Act
        result = properties.wsi_format

        # Assert
        assert result is None


class TestFormatCoordinateDefaults:
    @pytest.mark.parametrize("wsi_format", list(WsiFormat), ids=lambda f: f.name)
    def test_defined_for_all_formats(self, wsi_format: WsiFormat):
        # Arrange

        # Act
        result = FormatCoordinateDefaults.from_wsi_format(wsi_format)

        # Assert
        assert isinstance(result, FormatCoordinateDefaults)

    @pytest.mark.parametrize("wsi_format", list(WsiFormat), ids=lambda f: f.name)
    def test_level_rotation_for_matches_defaults(self, wsi_format: WsiFormat):
        # Arrange
        expected = FormatCoordinateDefaults.from_wsi_format(wsi_format).level_rotation

        # Act
        result = FormatCoordinateDefaults.level_rotation_for(wsi_format)

        # Assert
        assert result == expected

    @pytest.mark.parametrize("wsi_format", list(WsiFormat), ids=lambda f: f.name)
    def test_rotations_are_supported(self, wsi_format: WsiFormat):
        # Arrange
        defaults = FormatCoordinateDefaults.from_wsi_format(wsi_format)

        # Act
        rotations = (
            defaults.level_rotation,
            defaults.label_rotation,
            defaults.overview_rotation,
        )

        # Assert
        for rotation in rotations:
            assert rotation is None or rotation in SUPPORTED_ROTATIONS

    @pytest.mark.parametrize("wsi_format", list(WsiFormat), ids=lambda f: f.name)
    def test_coordinate_systems_resolve(self, wsi_format: WsiFormat):
        # Arrange
        defaults = FormatCoordinateDefaults.from_wsi_format(wsi_format)

        # Act
        level = defaults.level_coordinate_system()
        label = defaults.label_coordinate_system()
        overview = defaults.overview_coordinate_system()

        # Assert
        assert isinstance(level, ImageCoordinateSystem)
        for system in (label, overview):
            assert system is None or isinstance(system, ImageCoordinateSystem)

    def test_level_delegates_to_default_for(self):
        # Arrange
        defaults = FormatCoordinateDefaults(180.0, None, None)

        # Act
        result = defaults.level_coordinate_system()

        # Assert
        assert result == ImageCoordinateSystem.default_for(180.0, ImageType.VOLUME)

    @pytest.mark.parametrize(
        ["rotation", "expected_origin"],
        [(0.0, PointMm(0, 0)), (180.0, PointMm(25, 50))],
    )
    def test_level_origin_matches_rotation(
        self, rotation: float, expected_origin: PointMm
    ):
        # Arrange
        defaults = FormatCoordinateDefaults(rotation, None, None)

        # Act
        result = defaults.level_coordinate_system()

        # Assert
        assert result.origin == expected_origin
        assert result.rotation == rotation

    def test_label_none_when_rotation_none(self):
        # Arrange
        defaults = FormatCoordinateDefaults(0.0, None, None)

        # Act
        result = defaults.label_coordinate_system()

        # Assert
        assert result is None

    def test_label_delegates_to_default_for(self):
        # Arrange
        defaults = FormatCoordinateDefaults(0.0, 0.0, None)

        # Act
        result = defaults.label_coordinate_system()

        # Assert
        assert result == ImageCoordinateSystem.default_for(0.0, ImageType.LABEL)

    def test_overview_none_when_rotation_none(self):
        # Arrange
        defaults = FormatCoordinateDefaults(0.0, None, None)

        # Act
        result = defaults.overview_coordinate_system()

        # Assert
        assert result is None

    def test_overview_delegates_to_default_for(self):
        # Arrange
        defaults = FormatCoordinateDefaults(0.0, None, 0.0)

        # Act
        result = defaults.overview_coordinate_system()

        # Assert
        assert result == ImageCoordinateSystem.default_for(0.0, ImageType.OVERVIEW)
