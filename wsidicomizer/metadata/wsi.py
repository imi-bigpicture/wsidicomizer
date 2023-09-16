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
from typing import List, Optional

from pydicom.uid import UID, generate_uid
from wsidicomizer.metadata.image import Image

from wsidicomizer.metadata.base_model import BaseModel
from wsidicomizer.metadata.equipment import Equipment
from wsidicomizer.metadata.label import Label
from wsidicomizer.metadata.optical_path import OpticalPath
from wsidicomizer.metadata.patient import Patient
from wsidicomizer.metadata.series import Series
from wsidicomizer.metadata.slide import Slide
from wsidicomizer.metadata.study import Study


# TODO figure out how metadata defined here can override or be overridden by
# *ImageMeta*. Suggestion is to have a bool flag on each module, indicating if the
# properties defined in that module should override metadata from file.
# Could additionally add a *override* dict that specifies individual attributes that
# should override metadata from file. All attributes not set to override will be
# overridden by attributes from file.

# Use case 1: User wants to set the attributes in Equipment so that no attributes from
# file is used (User does not want to make it to easy to figure out what scanner was
# used). User would then set the override-property of the Equpment object to True.

# Use case 2: User wants to set the device serial number attribute in Equipment, but
# allow the other attributes to be filled in from file. User would then set the
# value for key 'device_serial_number' in the override_property-dictionary to True.

# The same override-dictionary could be used in all modules, e.g. one could create a
# override-dictionary:
# overrides = {
#   'device_serial_number': True,
#   'text': True
# }
# And feed this to all modules.

# The modules primarily contain type 1 and 2 attributes, but also some 3 and some
# conditional attributes. They way they are currently converted to dataset, there is no
# check that type 1 attributes are not empty, or that type 3 attributes are not included
# if empty, or if conditional attributes are set. The straight forward way is likely to
# change to model-specific to_dataset()-methods.

# Names in DICOM has a specific format, which is not super intuitive to make from
# scratch. Maybe use the pydicom dicom name class, as one can then use its helper
# function to format the name correctly.


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
    dimension_organization_uid: Optional[UID] = None

    @cached_property
    def _frame_of_reference_uid(self) -> UID:
        if self.frame_of_reference_uid is not None:
            return self.frame_of_reference_uid
        return generate_uid()

    @cached_property
    def _dimension_organization_uid(self) -> UID:
        if self.dimension_organization_uid is not None:
            return self.dimension_organization_uid
        return generate_uid()
