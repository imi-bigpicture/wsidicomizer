import datetime
from typing import Optional

from pydicom import Dataset
from pydicom.uid import UID, generate_uid
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base import (
    DicomDateTimeAttribute,
    DicomModelBase,
    DicomStringAttribute,
    DicomUidAttribute,
)


class Study(DicomModelBase):
    """
    Study metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    General Study Module:
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part03/sect_C.7.2.html
    """

    def __init__(
        self,
        uid: Optional[UID] = None,
        identifier: Optional[str] = None,
        date: Optional[datetime.date] = None,
        time: Optional[datetime.time] = None,
        accession_number: Optional[str] = None,
        referring_physician_name: Optional[str] = None,
    ):
        self._uid = DicomUidAttribute("StudyInstanceUID", True, uid, generate_uid)
        self._identifier = DicomStringAttribute("StudyId", True, identifier)
        self._date = DicomDateTimeAttribute("StudyDate", True, date)
        self._time = DicomDateTimeAttribute("StudyTime", True, time)
        self._accession_number = DicomStringAttribute(
            "AccessionNumber", True, accession_number
        )
        self._referring_physician_name = DicomStringAttribute(
            "ReferringPhysicianName", True, referring_physician_name
        )

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        self._insert_dicom_attributes_into_dataset(dataset)
