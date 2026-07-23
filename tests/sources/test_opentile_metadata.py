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
from decoy import Decoy
from opentile import Metadata
from PIL import ImageCms
from wsidicom.geometry import SizeMm

from wsidicomizer.sources.opentile.opentile_metadata import OpenTileMetadata
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat


@pytest.fixture
def opentile_metadata(decoy: Decoy) -> Metadata:
    """Opentile Metadata mock with every field absent; tests override as needed."""
    metadata = decoy.mock(cls=Metadata)
    decoy.when(metadata.scanner_manufacturer).then_return(None)
    decoy.when(metadata.scanner_model).then_return(None)
    decoy.when(metadata.scanner_serial_number).then_return(None)
    decoy.when(metadata.scanner_software_versions).then_return(None)
    decoy.when(metadata.acquisition_datetime).then_return(None)
    decoy.when(metadata.magnification).then_return(None)
    decoy.when(metadata.label_text).then_return(None)
    decoy.when(metadata.barcode).then_return(None)
    decoy.when(metadata.properties).then_return({})
    return metadata


class TestOpenTileMetadata:
    def test_magnification_populates_objective_power(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.magnification).then_return(20.0)

        # Act
        result = OpenTileMetadata(
            opentile_metadata, has_label=False, has_overview=False
        )

        # Assert
        optical_paths = result.pyramid.optical_paths
        assert len(optical_paths) == 1
        assert optical_paths[0].objective is not None
        assert optical_paths[0].objective.objective_power == 20.0

    def test_no_magnification_no_optical_path(self, opentile_metadata: Metadata):
        # Arrange
        # (magnification defaults to None via fixture)

        # Act
        result = OpenTileMetadata(
            opentile_metadata, has_label=False, has_overview=False
        )

        # Assert
        assert result.pyramid.optical_paths == []

    def test_magnification_and_icc_share_one_optical_path(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.magnification).then_return(20.0)
        icc_profile = b"icc-bytes"

        # Act
        result = OpenTileMetadata(
            opentile_metadata,
            has_label=False,
            has_overview=False,
            icc_profile=icc_profile,
        )

        # Assert
        optical_paths = result.pyramid.optical_paths
        assert len(optical_paths) == 1
        assert optical_paths[0].icc_profile == icc_profile
        assert optical_paths[0].objective is not None
        assert optical_paths[0].objective.objective_power == 20.0

    def test_icc_only_optical_path_has_no_objective(self, opentile_metadata: Metadata):
        # Arrange
        # (magnification defaults to None via fixture)
        icc_profile = b"icc-bytes"

        # Act
        result = OpenTileMetadata(
            opentile_metadata,
            has_label=False,
            has_overview=False,
            icc_profile=icc_profile,
        )

        # Assert
        optical_paths = result.pyramid.optical_paths
        assert len(optical_paths) == 1
        assert optical_paths[0].icc_profile == icc_profile
        assert optical_paths[0].objective is None

    def test_color_space_populated_from_icc(self, opentile_metadata: Metadata):
        # Arrange
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
        expected = ImageCms.getProfileDescription(profile).strip()

        # Act
        result = OpenTileMetadata(
            opentile_metadata,
            has_label=False,
            has_overview=False,
            icc_profile=profile.tobytes(),
        )

        # Assert
        assert result.pyramid.optical_paths[0].color_space == expected

    def test_equipment_from_scanner_metadata(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.scanner_manufacturer).then_return("maker")
        decoy.when(opentile_metadata.scanner_model).then_return("model")
        decoy.when(opentile_metadata.scanner_serial_number).then_return("serial")
        decoy.when(opentile_metadata.scanner_software_versions).then_return(["v1"])

        # Act
        result = OpenTileMetadata(
            opentile_metadata, has_label=False, has_overview=False
        )

        # Assert
        assert result.equipment.manufacturer == "maker"
        assert result.equipment.model_name == "model"
        assert result.equipment.device_serial_number == "serial"
        assert result.equipment.software_versions == ["v1"]

    def test_acquisition_datetime_from_metadata(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        acquired = datetime(2026, 6, 22, 12, 0, 0)
        decoy.when(opentile_metadata.acquisition_datetime).then_return(acquired)

        # Act
        result = OpenTileMetadata(
            opentile_metadata, has_label=False, has_overview=False
        )

        # Assert
        assert result.pyramid.image.acquisition_datetime == acquired

    def test_label_created_when_has_label(self, opentile_metadata: Metadata):
        # Arrange

        # Act
        result = OpenTileMetadata(opentile_metadata, has_label=True, has_overview=False)

        # Assert
        assert result.label is not None
        assert result.label.image is not None

    def test_no_label_image_when_not_has_label(self, opentile_metadata: Metadata):
        # Arrange

        # Act
        result = OpenTileMetadata(
            opentile_metadata, has_label=False, has_overview=False
        )

        # Assert
        assert result.label is None or result.label.image is None

    def test_label_text_populates_label_without_label_image(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.label_text).then_return("SR1274-908A")

        # Act
        result = OpenTileMetadata(
            opentile_metadata, has_label=False, has_overview=False
        )

        # Assert
        assert result.label is not None
        assert result.label.text == "SR1274-908A"
        assert result.label.image is None

    def test_barcode_populates_label(self, decoy: Decoy, opentile_metadata: Metadata):
        # Arrange
        decoy.when(opentile_metadata.barcode).then_return("SR1274-908A")

        # Act
        result = OpenTileMetadata(opentile_metadata, has_label=True, has_overview=False)

        # Assert
        assert result.label is not None
        assert result.label.barcode == "SR1274-908A"

    def test_barcode_populates_label_without_label_image(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.barcode).then_return("SR1274-908A")

        # Act
        result = OpenTileMetadata(
            opentile_metadata, has_label=False, has_overview=False
        )

        # Assert
        assert result.label is not None
        assert result.label.barcode == "SR1274-908A"
        assert result.label.image is None

    def test_barcode_dropped_when_not_include_confidential(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.barcode).then_return("SR1274-908A")
        result = OpenTileMetadata(opentile_metadata, has_label=True, has_overview=False)

        # Act
        merged = result.merge(None, None, include_confidential=False)

        # Assert
        assert merged.label is None or merged.label.barcode is None

    def test_label_text_kept_when_include_confidential(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.label_text).then_return("SR1274-908A")
        result = OpenTileMetadata(opentile_metadata, has_label=True, has_overview=False)

        # Act
        merged = result.merge(None, None, include_confidential=True)

        # Assert
        assert merged.label is not None
        assert merged.label.text == "SR1274-908A"

    def test_label_text_dropped_when_not_include_confidential(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.label_text).then_return("SR1274-908A")
        result = OpenTileMetadata(opentile_metadata, has_label=True, has_overview=False)

        # Act
        merged = result.merge(None, None, include_confidential=False)

        # Assert
        assert merged.label is None or merged.label.text is None

    def test_overview_created_when_has_overview(self, opentile_metadata: Metadata):
        # Arrange

        # Act
        result = OpenTileMetadata(opentile_metadata, has_label=False, has_overview=True)

        # Assert
        assert result.overview is not None

    def test_no_overview_when_not_has_overview(self, opentile_metadata: Metadata):
        # Arrange

        # Act
        result = OpenTileMetadata(
            opentile_metadata, has_label=False, has_overview=False
        )

        # Assert
        assert result.overview is None

    def test_ndpi_offsets_place_level_on_slide(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        # CMU-1.ndpi: imaged region center 4.877 mm right of and 2.340 mm above the
        # center of the slide, in the stored image direction.
        decoy.when(opentile_metadata.properties).then_return(
            {
                "x_offset_from_slide_center": 4876667,
                "y_offset_from_slide_center": -2340000,
            }
        )

        # Act
        result = OpenTileMetadata(
            opentile_metadata,
            has_label=False,
            has_overview=False,
            wsi_format=WsiFormat.NDPI,
            imaged_size=SizeMm(23.37, 17.36),
        )

        # Assert
        image_coordinate_system = result.pyramid.image.image_coordinate_system
        assert image_coordinate_system is not None
        assert image_coordinate_system.rotation == 180.0
        assert image_coordinate_system.origin.x == pytest.approx(23.520, abs=0.001)
        assert image_coordinate_system.origin.y == pytest.approx(44.308, abs=0.001)

    def test_ndpi_without_offsets_falls_back_to_default(
        self, opentile_metadata: Metadata
    ):
        # Arrange
        # (properties default to empty via fixture)

        # Act
        result = OpenTileMetadata(
            opentile_metadata,
            has_label=False,
            has_overview=False,
            wsi_format=WsiFormat.NDPI,
            imaged_size=SizeMm(23.37, 17.36),
        )

        # Assert
        assert (
            result.pyramid.image.image_coordinate_system
            == FormatCoordinateDefaults.from_wsi_format(
                WsiFormat.NDPI
            ).level_coordinate_system()
        )

    def test_offsets_ignored_for_other_formats(
        self, decoy: Decoy, opentile_metadata: Metadata
    ):
        # Arrange
        decoy.when(opentile_metadata.properties).then_return(
            {
                "x_offset_from_slide_center": 4876667,
                "y_offset_from_slide_center": -2340000,
            }
        )

        # Act
        result = OpenTileMetadata(
            opentile_metadata,
            has_label=False,
            has_overview=False,
            wsi_format=WsiFormat.SVS,
            imaged_size=SizeMm(23.37, 17.36),
        )

        # Assert
        assert (
            result.pyramid.image.image_coordinate_system
            == FormatCoordinateDefaults.from_wsi_format(
                WsiFormat.SVS
            ).level_coordinate_system()
        )
