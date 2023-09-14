import pytest

from wsidicomizer.metadata.equipment import Equipment
from wsidicomizer.metadata.patient import Patient
from wsidicomizer.metadata.series import Series
from wsidicomizer.metadata.study import Study
from wsidicomizer.metadata.wsi import WsiMetadata


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
        merged = Equipment.merge(base_equipment, user_equipment, default_equipment)

        # Assert
        assert merged is not None
        assert merged.manufacturer == user_equipment.manufacturer
        assert merged.model_name == base_equipment.model_name
        assert merged.device_serial_number == default_equipment.device_serial_number
        assert merged.software_versions == None

    def test_merge_nested(
        self,
        base_equipment: Equipment,
        user_equipment: Equipment,
        default_equipment: Equipment,
        study: Study,
        series: Series,
        patient: Patient,
    ):
        base = WsiMetadata(equipment=base_equipment, series=series)
        user = WsiMetadata(equipment=user_equipment, study=study)
        default = WsiMetadata(equipment=default_equipment, patient=patient)

        # Act
        merged = WsiMetadata.merge(base, user, default)

        # Assert
        assert merged is not None
        assert merged.equipment is not None
        assert merged.equipment.manufacturer == user_equipment.manufacturer
        assert merged.equipment.model_name == base_equipment.model_name
        assert (
            merged.equipment.device_serial_number
            == default_equipment.device_serial_number
        )
        assert merged.equipment.software_versions == None
        assert merged.study == study
        assert merged.series == series
        assert merged.patient == patient
