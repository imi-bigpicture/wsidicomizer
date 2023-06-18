"""Study model."""
from dataclasses import dataclass
import datetime
from typing import Dict, List, Optional

from pydicom import Dataset
from pydicom.uid import UID, generate_uid
from wsidicom.instance import ImageType

from wsidicomizer.metadata.model_base import (
    ModelBase,
)

from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomUidAttribute,
    DicomDateTimeAttribute,
    DicomStringAttribute,
)
from wsidicomizer.metadata.fields import FieldFactory


@dataclass
class Study(ModelBase):
    """
    Study metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    General Study Module:
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part03/sect_C.7.2.html
    """

    uid: Optional[UID] = FieldFactory.uid_field()
    identifier: Optional[str] = None
    date: Optional[datetime.date] = FieldFactory.date_field()
    time: Optional[datetime.time] = FieldFactory.time_field()
    accession_number: Optional[str] = None
    referring_physician_name: Optional[str] = None
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomUidAttribute("StudyInstanceUID", True, self.uid, generate_uid),
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
