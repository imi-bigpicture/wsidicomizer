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

import datetime
from dataclasses import dataclass

from wsidicom.conceptcode import (
    ContainerComponentTypeCode,
    ContainerTypeCode,
    IlluminationCode,
    IlluminationColorCode,
)
from wsidicom.geometry import PointMm

from wsidicomizer.metadata.image import FocusMethod


@dataclass
class Defaults:
    string = "Unknown"
    date_time = datetime.datetime(1, 1, 1)
    illumination_type = IlluminationCode("Brightfield illumination")
    illumination = IlluminationColorCode("Full Spectrum")
    slide_container_type = ContainerTypeCode("Microscope slide")
    slide_component_type = ContainerComponentTypeCode("Microscope slide cover slip")
    slide_material = "GLASS"
    focus_method = FocusMethod.AUTO
    image_coordinate_system_origin = PointMm(0, 0)
    image_coordinate_system_rotation = 0


defaults = Defaults()
