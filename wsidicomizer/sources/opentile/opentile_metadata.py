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

from typing import Optional

from opentile import Metadata
from wsidicom.metadata import Equipment, Image, Label, OpticalPath, Overview, Pyramid

from wsidicomizer.metadata import WsiDicomizerMetadata


class OpenTileMetadata(WsiDicomizerMetadata):
    def __init__(
        self,
        metadata: Metadata,
        has_label: bool,
        has_overview: bool,
        icc_profile: Optional[bytes] = None,
    ):
        equipment = Equipment(
            metadata.scanner_manufacturer,
            metadata.scanner_model,
            metadata.scanner_serial_number,
            metadata.scanner_software_versions,
        )
        image = Image(metadata.aquisition_datetime)
        if icc_profile is not None:
            optical_path = OpticalPath(icc_profile=icc_profile)
            optical_paths = [optical_path]
        else:
            optical_paths = []
        pyramid = Pyramid(image=image, optical_paths=optical_paths)
        if has_label:
            label = Label(image=Image(metadata.aquisition_datetime), optical_paths=[])
        else:
            label = None
        if has_overview:
            overview = Overview(
                image=Image(metadata.aquisition_datetime),
                optical_paths=[],
            )
        else:
            overview = None
        super().__init__(
            equipment=equipment, pyramid=pyramid, label=label, overview=overview
        )
