from re import M
from typing import Optional, Sequence
from pydicom import Dataset
import pytest

from tests.conftest import equipment
from wsidicomizer.metadata.equipment import Equipment


class TestFromDataset:
    @pytest.mark.parametrize(
        ["manufacturer", "model_name", "serial_number", "versions"],
        [
            ["manufacturer", "model_name", "serial_number", ["version"]],
            ["manufacturer", "model_name", "serial_number", ["version 1", "version 2"]],
            [None, None, None, None],
        ],
    )
    def test_equipment(
        self,
        manufacturer: Optional[str],
        model_name: Optional[str],
        serial_number: Optional[str],
        versions: Optional[Sequence[str]],
    ):
        # Arrange
        dataset = Dataset()
        dataset.Manufacturer = manufacturer
        dataset.ManufacturerModelName = model_name
        dataset.DeviceSerialNumber = serial_number
        dataset.SoftwareVersions = versions

        # Act
        equipment = Equipment.from_dataset(dataset)

        # Assert
        assert equipment.manufacturer == manufacturer
        assert equipment.model_name == model_name
        assert equipment.device_serial_number == serial_number
        assert equipment.software_versions == versions
