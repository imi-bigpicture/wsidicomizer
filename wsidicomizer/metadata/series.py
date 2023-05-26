from typing import Optional

from pydicom import Dataset
from pydicom.uid import UID, generate_uid
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base import (
    DicomModelBase,
    DicomStringAttribute,
    DicomUidAttribute,
)


class Series(DicomModelBase):
    """
    Series metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    Common Series Module:
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part03/sect_C.7.3.html

    The `Modality` attribute is fixed to `SM`.
    """

    def __init__(self, uid: Optional[UID] = None, number: Optional[int] = None):
        self._uid = DicomUidAttribute("SeriesInstanceUID", True, uid, generate_uid)
        self._number = DicomStringAttribute("SeriesNumber", True, uid)

        self._dicom_attributes = [self._uid, self._number]

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        self._insert_dicom_attributes_into_dataset(dataset)
