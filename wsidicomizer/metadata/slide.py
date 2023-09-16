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

"""Slide model."""
from dataclasses import dataclass
from typing import Sequence, Optional, Sequence


from wsidicomizer.metadata.base_model import BaseModel

from wsidicomizer.metadata.sample import SlideSample, Staining


@dataclass
class Slide(BaseModel):
    """
    Metadata for a slide.

    A slide has a an identifier and contains one or more samples. The position of the
    samples can be specified using a SampleLocation. All the samples on the slide has
    been stained with the sample list of stainings.
    """

    identifier: Optional[str] = None
    stainings: Optional[Sequence[Staining]] = None
    samples: Optional[Sequence[SlideSample]] = None
