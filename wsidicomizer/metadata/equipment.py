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

"""Equipment model."""

from dataclasses import dataclass

from wsidicomizer.metadata.defaults import defaults

from typing import List, Optional, Sequence

from pydicom import Dataset
from wsidicom.instance import ImageType

from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomListStringAttribute,
    DicomStringAttribute,
)
from wsidicomizer.metadata.base_model import BaseModel


@dataclass
class Equipment(BaseModel):
    """
    Equipment used to produce the slide.

    Corresponds to the `Required` attributes in the Enhanced General Equipment Module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.5.2.html
    """

    manufacturer: Optional[str] = None
    model_name: Optional[str] = None
    device_serial_number: Optional[str] = None
    software_versions: Optional[Sequence[str]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomStringAttribute(
                "Manufacturer",
                True,
                self.manufacturer,
                defaults.string,
            ),
            DicomStringAttribute(
                "ManufacturerModelName",
                True,
                self.model_name,
                defaults.string,
            ),
            DicomStringAttribute(
                "DeviceSerialNumber",
                True,
                self.device_serial_number,
                defaults.string,
            ),
            DicomListStringAttribute(
                "SoftwareVersions",
                True,
                self.software_versions,
                [defaults.string],
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "Equipment":
        software_versions = dataset.get("SoftwareVersions", None)
        if isinstance(software_versions, str):
            software_versions = [software_versions]
        return cls(
            dataset.Manufacturer,
            dataset.ManufacturerModelName,
            dataset.DeviceSerialNumber,
            software_versions,
        )
