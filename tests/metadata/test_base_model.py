#    Copyright 2023 SECTRA AB
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
from wsidicom.metadata import (
    Equipment,
    Image,
    Label,
    Patient,
    Series,
    Slide,
    Study,
    WsiMetadata,
)

from wsidicomizer.metadata import WsiDicomizerMetadata


@pytest.fixture
def base_equipment():
    yield Equipment("base", "base", None, None)


@pytest.fixture
def user_equipment():
    yield Equipment("user", None, None, None)


@pytest.fixture
def default_equipment():
    yield Equipment("default", "default", "default", None)


class TestMetadataMerge:
    def test_merge_simple(
        self,
        base_equipment: Equipment,
        user_equipment: Equipment,
        default_equipment: Equipment,
    ):
        # Arrange

        # Act
        merged = WsiDicomizerMetadata._merge(
            Equipment, base_equipment, user_equipment, default_equipment
        )

        # Assert
        assert merged is not None
        assert merged.manufacturer == user_equipment.manufacturer
        assert merged.model_name == base_equipment.model_name
        assert merged.device_serial_number == default_equipment.device_serial_number
        assert merged.software_versions is None

    def test_merge_nested(
        self,
        base_equipment: Equipment,
        user_equipment: Equipment,
        default_equipment: Equipment,
        study: Study,
        series: Series,
        patient: Patient,
    ):
        base = WsiDicomizerMetadata(
            study=Study(),
            series=series,
            patient=Patient(),
            equipment=base_equipment,
            optical_paths=[],
            slide=Slide(),
            label=Label(),
            image=Image(),
        )
        user = WsiMetadata(
            study=study,
            series=Series(),
            patient=Patient(),
            equipment=user_equipment,
            optical_paths=[],
            slide=Slide(),
            label=Label(),
            image=Image(),
        )
        default = WsiMetadata(
            study=study,
            series=Series(),
            patient=patient,
            equipment=default_equipment,
            optical_paths=[],
            slide=Slide(),
            label=Label(),
            image=Image(),
        )

        # Act
        merged = base.merge(user, default, True)

        # Assert
        assert merged is not None
        assert merged.equipment is not None
        assert merged.equipment.manufacturer == user_equipment.manufacturer
        assert merged.equipment.model_name == base_equipment.model_name
        assert (
            merged.equipment.device_serial_number
            == default_equipment.device_serial_number
        )
        assert merged.equipment.software_versions is None
        assert merged.study == study
        assert merged.series == series
        assert merged.patient == patient
