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

from opentile import Metadata as OpenTileMetadata
from wsidicom.geometry import PointMm

from wsidicomizer.metadata import WsiMetadata
from wsidicomizer.metadata.equipment import Equipment
from wsidicomizer.metadata.image import Image, ImageCoordinateSystem


class OpentileMetadata(WsiMetadata):
    def __init__(self, metadata: OpenTileMetadata):
        self.equipment = Equipment(
            metadata.scanner_manufacturer,
            metadata.scanner_model,
            metadata.scanner_serial_number,
            metadata.scanner_software_versions,
        )
        image_coordinate_system = None
        if metadata.image_offset is not None:
            image_coordinate_system = ImageCoordinateSystem(
                origin=PointMm(metadata.image_offset[0], metadata.image_offset[1]),
                rotation=0,
            )
        self.image = Image(
            metadata.aquisition_datetime,
            image_coordinate_system=image_coordinate_system,
        )