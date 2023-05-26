from dataclasses import dataclass
from typing import Iterable, List, Optional

from pydicom import Dataset
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base import (
    DicomAttribute,
    DicomListStringAttribute,
    DicomModelBase,
    DicomStringAttribute,
)


class Equipment(DicomModelBase):
    """
    Equipment used to produce the slide.

    Corresponds to the `Required` attributes in the Enhanced General Equipment Module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.5.2.html
    """

    def __init__(
        self,
        manufacturer: Optional[str] = None,
        model_name: Optional[str] = None,
        device_serial_number: Optional[str] = None,
        software_versions: Optional[Iterable[str]] = None,
    ):
        self._manufacturer = DicomStringAttribute(
            "Manufacturer",
            True,
            manufacturer,
            self._default_string_value,
        )
        self._model_name = DicomStringAttribute(
            "ManufacturerModelName",
            True,
            model_name,
            self._default_string_value,
        )
        self._device_serial_number = DicomStringAttribute(
            "DeviceSerialNumber",
            True,
            device_serial_number,
            self._default_string_value,
        )
        self._software_versions = DicomListStringAttribute(
            "SoftwareVersions",
            True,
            software_versions,
            lambda: [self._default_string_value()],
        )
        self._dicom_attributes: List[DicomAttribute] = [
            self._manufacturer,
            self._model_name,
            self._device_serial_number,
            self._software_versions,
        ]

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        self._insert_dicom_attributes_into_dataset(dataset)
