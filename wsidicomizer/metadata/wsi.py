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

"""Complete WSI model."""
from dataclasses import dataclass, field
from functools import cached_property
from typing import List, Optional, Sequence

from pydicom.uid import UID, generate_uid

from wsidicomizer.metadata.base_model import BaseModel
from wsidicomizer.metadata.equipment import Equipment
from wsidicomizer.metadata.image import Image
from wsidicomizer.metadata.label import Label
from wsidicomizer.metadata.optical_path import OpticalPath
from wsidicomizer.metadata.patient import Patient
from wsidicomizer.metadata.series import Series
from wsidicomizer.metadata.slide import Slide
from wsidicomizer.metadata.study import Study


@dataclass
class WsiMetadata(BaseModel):
    study: Optional[Study] = None
    series: Optional[Series] = None
    patient: Optional[Patient] = None
    equipment: Optional[Equipment] = None
    optical_paths: List[OpticalPath] = field(default_factory=lambda: list())
    slide: Optional[Slide] = None
    label: Optional[Label] = None
    image: Optional[Image] = None
    frame_of_reference_uid: Optional[UID] = None
    dimension_organization_uids: Sequence[UID] = field(default_factory=lambda: list())

    @cached_property
    def _frame_of_reference_uid(self) -> UID:
        if self.frame_of_reference_uid is not None:
            return self.frame_of_reference_uid
        return generate_uid()

    @cached_property
    def _dimension_organization_uids(self) -> Sequence[UID]:
        if self.dimension_organization_uids is not None:
            return self.dimension_organization_uids
        return [generate_uid()]
