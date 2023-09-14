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

"""Label model."""
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydicom import Dataset
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base_model import BaseModel
from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomBoolAttribute,
    DicomStringAttribute,
)


@dataclass
class Label(BaseModel):
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
        label_module_required = image_type == ImageType.LABEL
        dicom_attributes: List[DicomAttribute] = [
            DicomBoolAttribute("BurnedInAnnotation", True, contains_phi),
            DicomBoolAttribute("SpecimenLabelInImage", True, label_in_image),
            DicomStringAttribute("LabelText", label_module_required, self.label_text),
            DicomStringAttribute(
                "BarcodeValue", label_module_required, self.barcode_value
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "Label":
        raise NotImplementedError()
