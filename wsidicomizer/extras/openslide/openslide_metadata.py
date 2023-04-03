#    Copyright 2021, 2022, 2023 SECTRA AB
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

"""Metadata for openslide file."""

from typing import Optional

from opentile import Metadata

from wsidicomizer.extras.openslide.openslide import (
    PROPERTY_NAME_OBJECTIVE_POWER,
    PROPERTY_NAME_VENDOR,
    OpenSlide,
)


class OpenSlideMetadata(Metadata):
    def __init__(self, slide: OpenSlide):
        magnification = slide.properties.get(PROPERTY_NAME_OBJECTIVE_POWER)
        if magnification is not None:
            self._magnification = float(magnification)
        else:
            self._magnification = None
        self._scanner_manufacturer = slide.properties.get(PROPERTY_NAME_VENDOR)

    @property
    def magnification(self) -> Optional[float]:
        return self._magnification

    @property
    def scanner_manufacturer(self) -> Optional[str]:
        return self._scanner_manufacturer
