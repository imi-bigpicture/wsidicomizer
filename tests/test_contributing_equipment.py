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

from importlib.metadata import version

import pytest
from wsidicom.conceptcode import ContributingEquipmentPurposeCode
from wsidicom.metadata import ContributingEquipment

from tests.conftest import FakeSource
from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.metadata import WsiDicomizerMetadata


@pytest.fixture
def acme() -> ContributingEquipment:
    return ContributingEquipment(
        purpose=ContributingEquipmentPurposeCode("Modifying Equipment"),
        manufacturer="ACME",
        model_name="acmeizer",
    )


@pytest.mark.unittest
class TestContributingEquipment:
    def test_states_wsidicomizer_as_modifying_equipment(self):
        # Act
        stated = DicomizerSource._contributing_equipment()

        # Assert
        assert stated.purpose == ContributingEquipmentPurposeCode("Modifying Equipment")
        assert stated.manufacturer == "wsidicomizer"
        assert stated.model_name == "wsidicomizer"
        assert stated.software_versions == [version("wsidicomizer")]
        assert stated.description == "Converted to DICOM WSI by wsidicomizer"
        assert stated.contribution_datetime is not None

    def test_is_stated_by_the_default_layer_when_nothing_else_states_any(self):
        # Arrange
        source = FakeSource(WsiDicomizerMetadata())

        # Act
        stated = source.metadata.contributing_equipment

        # Assert
        assert [equipment.manufacturer for equipment in stated] == ["wsidicomizer"]

    def test_the_default_layer_reports_what_it_states(self):
        # Arrange
        source = FakeSource(WsiDicomizerMetadata())

        # Act
        default = source.default_metadata

        # Assert
        assert [
            equipment.manufacturer for equipment in default.contributing_equipment
        ] == ["wsidicomizer"]

    def test_is_kept_alongside_what_the_caller_states(
        self, acme: ContributingEquipment
    ):
        # Arrange
        source = FakeSource(
            WsiDicomizerMetadata(),
            metadata=WsiDicomizerMetadata(contributing_equipment=[acme]),
        )

        # Act
        stated = source.metadata.contributing_equipment

        # Assert
        assert [equipment.manufacturer for equipment in stated] == [
            "ACME",
            "wsidicomizer",
        ]

    def test_is_left_out_by_what_the_callers_defaults_state(
        self, acme: ContributingEquipment
    ):
        # Arrange
        source = FakeSource(
            WsiDicomizerMetadata(),
            default_metadata=WsiDicomizerMetadata(contributing_equipment=[acme]),
        )

        # Act
        stated = source.metadata.contributing_equipment

        # Assert
        assert [equipment.manufacturer for equipment in stated] == ["ACME"]

    def test_is_stated_even_when_confidential_metadata_is_left_out(self):
        # Arrange
        source = FakeSource(WsiDicomizerMetadata(), include_confidential=False)

        # Act
        stated = source.metadata.contributing_equipment

        # Assert
        assert [equipment.manufacturer for equipment in stated] == ["wsidicomizer"]
