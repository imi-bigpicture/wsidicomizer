import datetime
from dataclasses import dataclass
from typing import List, Literal, Optional, Union

from pydicom.sr.coding import Code

from wsidicomizer.metadata.base import DicomModelBase


@dataclass
class Patient(DicomModelBase):
    patient_name: Optional[str] = None
    patient_id: Optional[str] = None
    patient_birth_date: Optional[datetime.date] = None
    patient_sex: Optional[Literal["F", "M", "O"]] = None
    patient_species_description: Optional[Union[str, Code]] = None
    patient_identity_removed: Optional[Literal["YES", "NO"]] = None
    deidentification_method: Optional[List[Union[str, Code]]] = None
