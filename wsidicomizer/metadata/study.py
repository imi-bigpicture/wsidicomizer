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

"""Study model."""
from dataclasses import dataclass
import datetime
from functools import cached_property
from typing import Dict, List, Optional

from pydicom import Dataset
from pydicom.uid import UID, generate_uid
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base_model import (
    BaseModel,
)

from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomUidAttribute,
    DicomDateTimeAttribute,
    DicomStringAttribute,
)


@dataclass
class Study(BaseModel):
    """
    Study metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    General Study Module:
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part03/sect_C.7.2.html
    """

    uid: Optional[UID] = None
    identifier: Optional[str] = None
    date: Optional[datetime.date] = None
    time: Optional[datetime.time] = None
    accession_number: Optional[str] = None
    referring_physician_name: Optional[str] = None

    @cached_property
    def _uid(self) -> UID:
        if self.uid is not None:
            return self.uid
        return generate_uid()

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomUidAttribute("StudyInstanceUID", True, self._uid),
            DicomStringAttribute("StudyID", True, self.identifier),
            DicomDateTimeAttribute("StudyDate", True, self.date),
            DicomDateTimeAttribute("StudyTime", True, self.time),
            DicomStringAttribute(
                "AccessionNumber",
                True,
                self.accession_number,
            ),
            DicomStringAttribute(
                "ReferringPhysicianName", True, self.referring_physician_name
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "Study":
        return cls(
            dataset.StudyInstanceUID,
            dataset.StudyID,
            dataset.StudyDate,
            dataset.StudyTime,
            dataset.AccessionNumber,
            dataset.ReferringPhysicianName,
        )
