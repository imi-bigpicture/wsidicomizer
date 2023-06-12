"""Series model."""
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydicom import Dataset
from pydicom.uid import UID, generate_uid
from wsidicom.instance import ImageType

from wsidicomizer.metadata.model_base import ModelBase
from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomNumberAttribute,
    DicomUidAttribute,
)
from wsidicomizer.metadata.fields import FieldFactory


@dataclass
class Series(ModelBase):
    """
    Series metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    Common Series Module:
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part03/sect_C.7.3.html

    The `Modality` attribute is fixed to `SM`.
    """

    uid: Optional[UID] = FieldFactory.uid_field()
    number: Optional[int] = None
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomUidAttribute("SeriesInstanceUID", True, self.uid, generate_uid),
            DicomNumberAttribute("SeriesNumber", True, self.number),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)
