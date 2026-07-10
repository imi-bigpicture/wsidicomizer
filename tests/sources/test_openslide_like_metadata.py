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
from PIL import ImageCms
from wsidicom.geometry import SizeMm

from wsidicomizer.sources.openslide_like.openslide_like_metadata import (
    OpenSlideLikeMetadata,
    OpenSlideLikeProperties,
)


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
