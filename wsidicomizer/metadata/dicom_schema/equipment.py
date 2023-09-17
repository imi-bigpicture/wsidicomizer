from typing import Type
from wsidicomizer.metadata.defaults import Defaults
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    DefaultingDicomField,
    ListDicomField,
)
from wsidicomizer.metadata.equipment import Equipment
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema

from marshmallow import fields


class EquipmentDicomSchema(DicomSchema):
    """
    Type 1:
    - manufacturer
    - model_name
    - device_serial_number
    - software_versions
    """

    manufacturer = DefaultingDicomField(
        fields.String(),
        dump_default=Defaults.string,
        load_default=None,
        data_key="Manufacturer",
    )
    model_name = DefaultingDicomField(
        fields.String(),
        dump_default=Defaults.string,
        load_default=None,
        data_key="ManufacturerModelName",
    )
    device_serial_number = DefaultingDicomField(
        fields.String(),
        dump_default=Defaults.string,
        load_default=None,
        data_key="DeviceSerialNumber",
    )
    software_versions = DefaultingDicomField(
        ListDicomField(fields.String()),
        dump_default=[Defaults.string],
        load_default=None,
        data_key="SoftwareVersions",
    )

    @property
    def load_type(self) -> Type[Equipment]:
        return Equipment
