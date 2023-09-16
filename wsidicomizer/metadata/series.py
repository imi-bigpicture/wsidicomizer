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

"""Series model."""
from dataclasses import dataclass
from functools import cached_property
from typing import Optional

from pydicom.uid import UID, generate_uid

from wsidicomizer.metadata.base_model import BaseModel


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
