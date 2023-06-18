"""Label model."""
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydicom import Dataset
from wsidicom.instance import ImageType

from wsidicomizer.metadata.model_base import ModelBase
from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomBoolAttribute,
    DicomStringAttribute,
)


@dataclass
class Label(ModelBase):
    """
    Label metadata.

    Corresponds to the `Required, Empty if Unknown` attributes in the Slide Label
    module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.12.8.html
    """

    label_text: Optional[str] = None
    barcode_value: Optional[str] = None
    label_in_volume_image: bool = False
    label_in_overview_image: bool = False
    label_is_phi: bool = True
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        label_in_image = False
        contains_phi = False
        if (
            (image_type == ImageType.VOLUME and self.label_in_volume_image)
            or (image_type == ImageType.OVERVIEW and self.label_in_overview_image)
            or image_type == ImageType.LABEL
        ):
            label_in_image = True
            contains_phi = self.label_is_phi
        dicom_attributes: List[DicomAttribute] = [
            DicomBoolAttribute("BurnedInAnnotation", True, contains_phi),
            DicomBoolAttribute("SpecimenLabelInImage", True, label_in_image),
        ]
        if image_type == ImageType.LABEL:
            dicom_attributes.extend(
                [
                    DicomStringAttribute("LabelText", True, self.label_text),
                    DicomStringAttribute("BarCodeValue", True, self.barcode_value),
                ]
            )
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "Label":
        raise NotImplementedError()
