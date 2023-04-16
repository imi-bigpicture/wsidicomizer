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

"""Metadata for opentile file."""

from typing import Any, Dict, Optional, Tuple

from opentile import Metadata

from wsidicomizer.metadata.image_metadata import ImageMetadata


class OpentileMetadata(ImageMetadata):
    def __init__(self, metadata: Metadata):
        self._metadata = metadata

    @property
    def properties(self) -> Dict[str, Any]:
        return {
            "Manufacturer": self._metadata.scanner_manufacturer,
            "ManufacturerModelName": self._metadata.scanner_model,
            "SoftwareVersions": self._metadata.scanner_software_versions,
            "DeviceSerialNumber": self._metadata.scanner_serial_number,
            "AcquisitionDateTime": self._metadata.aquisition_datetime,
        }

    @property
    def image_offset(self) -> Optional[Tuple[float, float]]:
        return self._metadata.image_offset
