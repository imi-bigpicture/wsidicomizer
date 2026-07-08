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

from dataclasses import replace
from importlib.metadata import version

import pytest
from wsidicom.conceptcode import ContributingEquipmentPurposeCode
from wsidicom.metadata import (
    ContributingEquipment,
    Equipment,
    Image,
    Label,
    Patient,
    Pyramid,
    Series,
    Study,
    WsiMetadata,
)
from wsidicom.metadata.slide import Slide

from wsidicomizer.dicomizer_source import DicomizerSource


@pytest.fixture
def metadata() -> WsiMetadata:
    return WsiMetadata(
        study=Study(),
        series=Series(),
        patient=Patient(),
        equipment=Equipment(),
        slide=Slide(),
        pyramid=Pyramid(image=Image(), optical_paths=[]),
        label=Label(),
    )


class TestContributingEquipment:
    def test_adds_wsidicomizer_as_modifying_equipment(self, metadata: WsiMetadata):
        # Act
        result = DicomizerSource._add_contributing_equipment(metadata)

        # Assert
        assert len(result.contributing_equipment) == 1
        item = result.contributing_equipment[0]
        assert item.purpose == ContributingEquipmentPurposeCode("Modifying Equipment")
        assert item.manufacturer == "wsidicomizer"
        assert item.model_name == "wsidicomizer"
        assert item.software_versions == [version("wsidicomizer")]
        assert item.description == "Converted to DICOM WSI by wsidicomizer"
        assert item.contribution_datetime is not None

    def test_appends_to_existing_contributing_equipment(self, metadata: WsiMetadata):
        # Arrange
        existing = ContributingEquipment(
            purpose=ContributingEquipmentPurposeCode("Modifying Equipment"),
            model_name="other",
        )
        metadata = replace(metadata, contributing_equipment=[existing])

        # Act
        result = DicomizerSource._add_contributing_equipment(metadata)

        # Assert
        assert len(result.contributing_equipment) == 2
        assert result.contributing_equipment[0] == existing
