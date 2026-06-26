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
from czifile import CziFile
from decoy import Decoy

from wsidicomizer.sources.czi.czi_metadata import CziMetadata


@pytest.fixture
def magnification(request: pytest.FixtureRequest) -> str | None:
    """Objective magnification; override per test with indirect parametrize."""
    return getattr(request, "param", "20")


@pytest.fixture
def scaling(request: pytest.FixtureRequest) -> str:
    """Pixel scaling in m/pixel (X and Y); override via indirect parametrize."""
    return getattr(request, "param", "1e-7")


@pytest.fixture
def scanner_model(request: pytest.FixtureRequest) -> str:
    return getattr(request, "param", "ScannerX")


@pytest.fixture
def application(request: pytest.FixtureRequest) -> tuple[str, str]:
    """Application (name, version)."""
    return getattr(request, "param", ("ZEN", "3.1"))


@pytest.fixture
def czi_metadata_xml(
    magnification: str | None,
    scaling: str,
    scanner_model: str,
    application: tuple[str, str],
) -> str:
    """Minimal CZI metadata XML covering everything CziMetadata reads on construction.

    A `magnification` of None omits NominalMagnification (the objective is still
    referenced, so magnification resolves to None).
    """
    nominal = (
        f"<NominalMagnification>{magnification}</NominalMagnification>"
        if magnification is not None
        else ""
    )
    application_name, application_version = application
    return f"""<ImageDocument>
      <Metadata>
        <Information>
          <Image>
            <AcquisitionDateAndTime>2026-06-22T12:00:00</AcquisitionDateAndTime>
            <MicroscopeRef Id="Microscope:1"/>
            <ObjectiveSettings>
              <ObjectiveRef Id="Objective:1"/>
            </ObjectiveSettings>
          </Image>
          <Instrument>
            <Microscopes>
              <Microscope Id="Microscope:1" Name="{scanner_model}"/>
            </Microscopes>
            <Objectives>
              <Objective Id="Objective:1">{nominal}</Objective>
            </Objectives>
          </Instrument>
          <Application>
            <Name>{application_name}</Name>
            <Version>{application_version}</Version>
          </Application>
        </Information>
        <Scaling>
          <Items>
            <Distance Id="X"><Value>{scaling}</Value></Distance>
            <Distance Id="Y"><Value>{scaling}</Value></Distance>
          </Items>
        </Scaling>
      </Metadata>
    </ImageDocument>"""


@pytest.fixture
def czi(decoy: Decoy, czi_metadata_xml: str) -> CziFile:
    czi = decoy.mock(cls=CziFile)
    decoy.when(czi.metadata()).then_return(czi_metadata_xml)
    return czi


class TestCziMetadata:
    def test_magnification_populates_objective_power(
        self, czi: CziFile, magnification: str
    ):
        # Arrange

        # Act
        result = CziMetadata(czi)

        # Assert
        optical_paths = result.pyramid.optical_paths
        assert len(optical_paths) == 1
        assert optical_paths[0].objective is not None
        assert optical_paths[0].objective.objective_power == float(magnification)

    @pytest.mark.parametrize("magnification", [None], indirect=True)
    def test_objective_power_none_when_magnification_missing(self, czi: CziFile):
        # Arrange

        # Act
        result = CziMetadata(czi)

        # Assert
        optical_paths = result.pyramid.optical_paths
        assert len(optical_paths) == 1
        assert optical_paths[0].objective is not None
        assert optical_paths[0].objective.objective_power is None

    def test_equipment_from_metadata(
        self, czi: CziFile, scanner_model: str, application: tuple[str, str]
    ):
        # Arrange
        expected_software_version = f"{application[0]} {application[1]}"

        # Act
        result = CziMetadata(czi)

        # Assert
        assert result.equipment.model_name == scanner_model
        assert result.equipment.software_versions == [expected_software_version]

    def test_pixel_spacing_from_scaling(self, czi: CziFile, scaling: str):
        # Arrange
        # Source converts m/pixel to mm/pixel (x 10^6, then / 1000).
        expected_pixel_spacing = float(scaling) * 1e6 / 1000

        # Act
        result = CziMetadata(czi)

        # Assert
        pixel_spacing = result.pyramid.image.pixel_spacing
        assert pixel_spacing is not None
        assert pixel_spacing.width == pytest.approx(expected_pixel_spacing)
        assert pixel_spacing.height == pytest.approx(expected_pixel_spacing)
