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

"""Image model."""
import datetime
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from wsidicom.geometry import Orientation, PointMm

from wsidicomizer.metadata.base_model import BaseModel


class FocusMethod(Enum):
    AUTO = "auto"
    MANUAL = "manual"


@dataclass
class ExtendedDepthOfField(BaseModel):
    number_of_focal_planes: int
    distance_between_focal_planes: float


@dataclass
class ImageCoordinateSystem(BaseModel):
    origin: PointMm
    rotation: float

    @property
    def orientation(self) -> Orientation:
        x = round(math.sin(self.rotation * math.pi / 180), 8)
        y = round(math.cos(self.rotation * math.pi / 180), 8)
        return Orientation([-x, y, 0, y, x, 0])


@dataclass
class Image(BaseModel):
    """
    Image metadata.

    Corresponds to the `Required, Empty if Unknown` attributes in the Slide Label
    module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.12.8.html
    """

    acquisition_datetime: Optional[datetime.datetime] = None
    focus_method: Optional[FocusMethod] = None
    extended_depth_of_field: Optional[ExtendedDepthOfField] = None
    image_coordinate_system: Optional[ImageCoordinateSystem] = None
