from dataclasses import dataclass
from typing import Optional

from pydicom import Dataset
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base import DicomModelBase, DicomStringAttribute


@dataclass
class Label(DicomModelBase):
    """
    Label metadata.

    Corresponds to the `Required, Empty if Unknown` attributes in the Slide Label
    module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.12.8.html
    """

    def __init__(
        self,
        label_text: Optional[str] = None,
        barcode_value: Optional[str] = None,
        label_in_volume_image: bool = False,
        label_in_overview_image: bool = False,
        label_is_phi: bool = True,
    ):
        self._label_text = DicomStringAttribute("LabelText", True, label_text)
        self._barcode_value = DicomStringAttribute("BarCodeValue", True, barcode_value)
        self._dicom_attributes = [self._label_text, self._barcode_value]
        self._label_in_volume_image = label_in_volume_image
        self._label_in_overview_image = label_in_overview_image
        self._label_is_phi = label_is_phi

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        if image_type == ImageType.LABEL:
            self._insert_dicom_attributes_into_dataset(dataset)

        label_in_image = False
        contains_phi = False
        if (
            (image_type == ImageType.VOLUME and self._label_in_volume_image)
            or (image_type == ImageType.OVERVIEW and self._label_in_overview_image)
            or image_type == ImageType.LABEL
        ):
            label_in_image = True
            contains_phi = self._label_is_phi
        dataset.BurnedInAnnotation = self._bool_to_literal(contains_phi)
        dataset.SpecimenLabelInImage = self._bool_to_literal(label_in_image)
