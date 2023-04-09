import datetime
from typing import Optional
from dataclasses import dataclass
from pydicom.uid import UID, generate_uid

from wsidicomizer.model.base import DicomModelBase


@dataclass
class Study(DicomModelBase):
    study_instance_uid: UID = generate_uid()
    study_id: Optional[str] = None
    study_date: Optional[datetime.date] = None
    study_time: Optional[datetime.date] = None
    accession_number: Optional[str] = None
    referring_physician_name: Optional[str] = None
