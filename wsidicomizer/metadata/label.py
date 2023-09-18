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
from typing import List, Optional

from wsidicomizer.metadata.base_model import BaseModel


@dataclass
class Label(BaseModel):
    """
    Label metadata.

    Corresponds to the `Required, Empty if Unknown` attributes in the Slide Label
    module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.12.8.html
    """

    text: Optional[str] = None
    barcode: Optional[str] = None
    label_in_volume_image: bool = False
    label_in_overview_image: bool = False
    label_is_phi: bool = True

    @classmethod
    def merge_image_types(
        cls, volume: "Label", label: Optional["Label"], overview: Optional["Label"]
    ):
        labels: List[Optional[Label]] = [label, volume, overview]
        text = next((item.text for item in labels if item is not None), None)
        barcode = next((item.barcode for item in labels if item is not None), None)
        label_is_phi = any(item.label_is_phi for item in labels if item is not None)
        if overview is None:
            label_in_overview_image = False
        else:
            label_in_overview_image = overview.label_in_overview_image
        return cls(
            text=text,
            barcode=barcode,
            label_in_volume_image=volume.label_in_volume_image,
            label_in_overview_image=label_in_overview_image,
            label_is_phi=label_is_phi,
        )
