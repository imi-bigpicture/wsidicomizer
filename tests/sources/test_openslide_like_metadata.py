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

from datetime import datetime

import pytest
from PIL import ImageCms
from wsidicom.geometry import PointMm, Size, SizeMm

from wsidicomizer.sources.openslide_like.openslide_like_metadata import (
    OpenSlideLikeMetadata,
    OpenSlideLikeProperties,
)
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat


@pytest.fixture
def color_profile() -> ImageCms.ImageCmsProfile:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))


class TestOpenSlideLikeMetadata:
    def test_objective_power_populates_optical_path(self):
        # Arrange
        properties = OpenSlideLikeProperties(objective_power="20")

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        optical_paths = result.pyramid.optical_paths
        assert len(optical_paths) == 1
        assert optical_paths[0].objective is not None
        assert optical_paths[0].objective.objective_power == 20.0

    def test_no_objective_power_no_optical_path(self):
        # Arrange
        properties = OpenSlideLikeProperties()

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.pyramid.optical_paths == []

    def test_objective_power_and_icc_share_one_optical_path(
        self, color_profile: ImageCms.ImageCmsProfile
    ):
        # Arrange
        properties = OpenSlideLikeProperties(objective_power="20")

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=color_profile)

        # Assert
        optical_paths = result.pyramid.optical_paths
        assert len(optical_paths) == 1
        assert optical_paths[0].icc_profile == color_profile.tobytes()
        assert optical_paths[0].objective is not None
        assert optical_paths[0].objective.objective_power == 20.0

    def test_icc_only_optical_path_has_no_objective(
        self, color_profile: ImageCms.ImageCmsProfile
    ):
        # Arrange
        properties = OpenSlideLikeProperties()

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=color_profile)

        # Assert
        optical_paths = result.pyramid.optical_paths
        assert len(optical_paths) == 1
        assert optical_paths[0].icc_profile == color_profile.tobytes()
        assert optical_paths[0].objective is None

    def test_color_space_populated_from_icc(
        self, color_profile: ImageCms.ImageCmsProfile
    ):
        # Arrange
        properties = OpenSlideLikeProperties()
        expected = ImageCms.getProfileDescription(color_profile).strip()

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=color_profile)

        # Assert
        assert result.pyramid.optical_paths[0].color_space == expected

    def test_equipment_manufacturer_from_vendor(self):
        # Arrange
        properties = OpenSlideLikeProperties(vendor="aperio")

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.equipment.manufacturer == "aperio"

    def test_pixel_spacing_from_mpp(self):
        # Arrange
        properties = OpenSlideLikeProperties(mpp_x="500", mpp_y="250")

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.pyramid.image.pixel_spacing == SizeMm(0.5, 0.25)

    def test_no_pixel_spacing_when_mpp_missing(self):
        # Arrange
        properties = OpenSlideLikeProperties()

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.pyramid.image.pixel_spacing is None

    def test_barcode_populates_label(self):
        # Arrange
        properties = OpenSlideLikeProperties(barcode="SR1274-908A")

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.label is not None
        assert result.label.barcode == "SR1274-908A"

    def test_barcode_populates_label_for_known_vendor(self):
        # Arrange
        properties = OpenSlideLikeProperties(vendor="hamamatsu", barcode="SR1274-908A")

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.label is not None
        assert result.label.barcode == "SR1274-908A"

    def test_no_barcode_and_unknown_vendor_gives_empty_label(self):
        # Arrange
        properties = OpenSlideLikeProperties()

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.label is not None
        assert result.label.barcode is None
        assert result.label.image is None

    def test_barcode_dropped_by_remove_confidential(self):
        # Arrange
        properties = OpenSlideLikeProperties(barcode="SR1274-908A")
        metadata = OpenSlideLikeMetadata(properties, color_profile=None)

        # Act
        result = metadata.remove_confidential()

        # Assert
        assert result.label is None or result.label.barcode is None

    @pytest.mark.parametrize("vendor", [None, "generic-tiff"])
    def test_image_placed_by_generic_defaults_when_vendor_missing_or_unrecognised(
        self, vendor: str | None
    ):
        # Arrange
        assert vendor not in OpenSlideLikeProperties.VENDOR_FORMATS, (
            f"{vendor!r} is now a recognised vendor, pick another for this test"
        )
        properties = OpenSlideLikeProperties(vendor=vendor)

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        image_coordinate_system = result.pyramid.image.image_coordinate_system
        assert image_coordinate_system is not None
        assert image_coordinate_system.rotation == 0.0
        assert image_coordinate_system.origin == PointMm(0.0, 0.0)
        assert result.overview is None

    def test_label_and_overview_dated_by_the_acquisition_datetime(self):
        # Arrange
        properties = OpenSlideLikeProperties(
            vendor="aperio",
            raw_properties={"aperio.Date": "01/02/20", "aperio.Time": "03:04:05"},
        )

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.label is not None
        assert result.label.image is not None
        assert result.label.image.acquisition_datetime == datetime(2020, 1, 2, 3, 4, 5)
        assert result.overview is not None
        assert result.overview.image is not None
        assert result.overview.image.acquisition_datetime == datetime(
            2020, 1, 2, 3, 4, 5
        )

    @pytest.mark.parametrize(
        ["x_offset", "y_offset"], [("4876667", "-2340000"), (4876667, -2340000)]
    )
    def test_ndpi_slide_centre_offset_places_level_on_slide(
        self, x_offset: str | int, y_offset: str | int
    ):
        # Arrange
        # CMU-1.ndpi: imaged region center 4.877 mm right of and 2.340 mm above the
        # center of the slide, in the stored image direction. openslide states the
        # offsets as str, tiffslide as int.
        properties = OpenSlideLikeProperties(
            vendor="hamamatsu",
            mpp_x="0.5",
            mpp_y="0.5",
            raw_properties={
                "hamamatsu.XOffsetFromSlideCentre": x_offset,  # pyright: ignore[reportArgumentType]
                "hamamatsu.YOffsetFromSlideCentre": y_offset,  # pyright: ignore[reportArgumentType]
            },
        )

        # Act
        result = OpenSlideLikeMetadata(
            properties, color_profile=None, base_size=Size(46740, 34720)
        )

        # Assert
        image_coordinate_system = result.pyramid.image.image_coordinate_system
        assert image_coordinate_system is not None
        assert image_coordinate_system.rotation == 180.0
        assert image_coordinate_system.origin.x == pytest.approx(23.520, abs=0.001)
        assert image_coordinate_system.origin.y == pytest.approx(44.308, abs=0.001)

    def test_ndpi_without_base_size_placed_by_format_defaults(self):
        # Arrange
        properties = OpenSlideLikeProperties(
            vendor="hamamatsu",
            mpp_x="0.5",
            mpp_y="0.5",
            raw_properties={
                "hamamatsu.XOffsetFromSlideCentre": "4876667",
                "hamamatsu.YOffsetFromSlideCentre": "-2340000",
            },
        )

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert (
            result.pyramid.image.image_coordinate_system
            == FormatCoordinateDefaults.from_wsi_format(
                WsiFormat.NDPI
            ).level_coordinate_system()
        )

    def test_ndpi_without_slide_centre_offset_placed_by_format_defaults(self):
        # Arrange
        properties = OpenSlideLikeProperties(
            vendor="hamamatsu", mpp_x="0.5", mpp_y="0.5"
        )

        # Act
        result = OpenSlideLikeMetadata(
            properties, color_profile=None, base_size=Size(46740, 34720)
        )

        # Assert
        assert (
            result.pyramid.image.image_coordinate_system
            == FormatCoordinateDefaults.from_wsi_format(
                WsiFormat.NDPI
            ).level_coordinate_system()
        )
