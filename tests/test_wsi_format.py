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
    def test_wsi_format_from_vendor(self, vendor, expected):
        assert OpenSlideLikeProperties(vendor=vendor).wsi_format == expected

    def test_wsi_format_no_vendor(self):
        assert OpenSlideLikeProperties(vendor=None).wsi_format is None


class TestFormatCoordinateDefaults:
    @pytest.mark.parametrize("wsi_format", list(WsiFormat), ids=lambda f: f.name)
    def test_defined_for_all_formats(self, wsi_format: WsiFormat):
        # Every WsiFormat must have an entry (no KeyError).
        assert isinstance(
            FormatCoordinateDefaults.from_wsi_format(wsi_format),
            FormatCoordinateDefaults,
        )

    @pytest.mark.parametrize("wsi_format", list(WsiFormat), ids=lambda f: f.name)
    def test_rotations_are_supported(self, wsi_format: WsiFormat):
        defaults = FormatCoordinateDefaults.from_wsi_format(wsi_format)
        for rotation in (
            defaults.level_rotation,
            defaults.label_rotation,
            defaults.overview_rotation,
        ):
            assert rotation is None or rotation in SUPPORTED_ROTATIONS

    @pytest.mark.parametrize("wsi_format", list(WsiFormat), ids=lambda f: f.name)
    def test_coordinate_systems_resolve(self, wsi_format: WsiFormat):
        defaults = FormatCoordinateDefaults.from_wsi_format(wsi_format)
        assert isinstance(defaults.level_coordinate_system(), ImageCoordinateSystem)
        for system in (
            defaults.label_coordinate_system(),
            defaults.overview_coordinate_system(),
        ):
            assert system is None or isinstance(system, ImageCoordinateSystem)

    def test_level_delegates_to_default_for(self):
        defaults = FormatCoordinateDefaults(180.0, None, None)
        assert defaults.level_coordinate_system() == ImageCoordinateSystem.default_for(
            180.0, ImageType.VOLUME
        )

    def test_level_origin_matches_rotation(self):
        volume_0 = FormatCoordinateDefaults(0.0, None, None).level_coordinate_system()
        assert (volume_0.origin, volume_0.rotation) == (PointMm(0, 0), 0.0)
        volume_180 = FormatCoordinateDefaults(
            180.0, None, None
        ).level_coordinate_system()
        assert (volume_180.origin, volume_180.rotation) == (PointMm(25, 50), 180.0)

    def test_label_none_when_rotation_none(self):
        assert (
            FormatCoordinateDefaults(0.0, None, None).label_coordinate_system() is None
        )

    def test_label_delegates_to_default_for(self):
        defaults = FormatCoordinateDefaults(0.0, 0.0, None)
        assert defaults.label_coordinate_system() == ImageCoordinateSystem.default_for(
            0.0, ImageType.LABEL
        )

    def test_overview_none_when_rotation_none(self):
        assert (
            FormatCoordinateDefaults(0.0, None, None).overview_coordinate_system()
            is None
        )

    def test_overview_delegates_to_default_for(self):
        defaults = FormatCoordinateDefaults(0.0, None, 0.0)
        assert (
            defaults.overview_coordinate_system()
            == ImageCoordinateSystem.default_for(0.0, ImageType.OVERVIEW)
        )
