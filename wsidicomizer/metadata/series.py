"""Series model."""
from dataclasses import dataclass
from functools import cached_property
from typing import Dict, List, Optional

from pydicom import Dataset
from pydicom.uid import UID, generate_uid
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base_model import BaseModel
from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomNumericAttribute,
    DicomUidAttribute,
)


@dataclass
class Series(BaseModel):
    """
    Series metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    Common Series Module:
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part03/sect_C.7.3.html

    The `Modality` attribute is fixed to `SM`.
    """

    uid: Optional[UID] = None
    number: Optional[int] = None

    @cached_property
    def _uid(self) -> UID:
        if self.uid is not None:
            return self.uid
        return generate_uid()

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomUidAttribute("SeriesInstanceUID", True, self._uid),
            DicomNumericAttribute("SeriesNumber", True, self.number),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "Series":
        return cls(dataset.SeriesInstanceUID, dataset.SeriesNumber)
