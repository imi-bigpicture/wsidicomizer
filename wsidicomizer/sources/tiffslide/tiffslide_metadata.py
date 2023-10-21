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

"""Metadata for tiffslide file."""

from tiffslide import TiffSlide
from tiffslide.tiffslide import PROPERTY_NAME_OBJECTIVE_POWER, PROPERTY_NAME_VENDOR

from wsidicom.metadata import WsiMetadata, Equipment, OpticalPath
from wsidicom.metadata.image import Image
from wsidicom.metadata.optical_path import Objectives
from wsidicom.metadata.series import Series
from wsidicom.metadata.study import Study
from pydicom.uid import generate_uid


class TiffSlideMetadata(WsiMetadata):
    image = Image()
    study = Study()
    series = Series()
    frame_of_reference_uid = generate_uid()
    dimension_organization_uid = generate_uid()

    def __init__(self, slide: TiffSlide):
        magnification = slide.properties.get(PROPERTY_NAME_OBJECTIVE_POWER)
        if magnification is not None:
            OpticalPath("0", objective=Objectives(objective_power=float(magnification)))
        self.equipment = Equipment(
            manufacturer=slide.properties.get(PROPERTY_NAME_VENDOR)
        )
