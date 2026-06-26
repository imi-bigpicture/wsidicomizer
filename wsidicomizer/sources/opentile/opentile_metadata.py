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

from opentile import Metadata
from wsidicom.metadata import (
    Equipment,
    Image,
    Label,
    Objectives,
    OpticalPath,
    Overview,
    Pyramid,
)

from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat


class OpenTileMetadata(WsiDicomizerMetadata):
    def __init__(
        self,
        metadata: Metadata,
        has_label: bool,
        has_overview: bool,
        icc_profile: bytes | None = None,
        wsi_format: WsiFormat | None = None,
    ):
        equipment = Equipment(
            metadata.scanner_manufacturer,
            metadata.scanner_model,
            metadata.scanner_serial_number,
            metadata.scanner_software_versions,
        )
        if wsi_format is not None:
            defaults = FormatCoordinateDefaults.from_wsi_format(wsi_format)
            image_coordinate_system = defaults.level_coordinate_system()
        else:
            defaults = None
            image_coordinate_system = None
        image = Image(
            metadata.aquisition_datetime,
            image_coordinate_system=image_coordinate_system,
        )
        objectives = (
            Objectives(objective_power=metadata.magnification)
            if metadata.magnification is not None
            else None
        )
        if objectives is not None or icc_profile is not None:
            optical_paths = [
                OpticalPath("0", objective=objectives, icc_profile=icc_profile)
            ]
        else:
            optical_paths = []
        pyramid = Pyramid(image=image, optical_paths=optical_paths)
        if has_label:
            label_image_coordinate_system = (
                defaults.label_coordinate_system() if defaults else None
            )
            label = Label(
                image=Image(
                    metadata.aquisition_datetime,
                    image_coordinate_system=label_image_coordinate_system,
                ),
                optical_paths=[],
            )
        else:
            label = None
        if has_overview:
            overview_image_coordinate_system = (
                defaults.overview_coordinate_system() if defaults else None
            )
            overview = Overview(
                image=Image(
                    metadata.aquisition_datetime,
                    image_coordinate_system=overview_image_coordinate_system,
                ),
                optical_paths=[],
            )
        else:
            overview = None
        super().__init__(
            equipment=equipment, pyramid=pyramid, label=label, overview=overview
        )
