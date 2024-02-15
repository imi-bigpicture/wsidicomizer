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

from typing import cast

from tiffslide import TiffSlide

from wsidicomizer.extras.openslide.openslide import (
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    PROPERTY_NAME_MPP_X,
    PROPERTY_NAME_MPP_Y,
    PROPERTY_NAME_OBJECTIVE_POWER,
    PROPERTY_NAME_VENDOR,
    OpenSlide,
)
from wsidicomizer.sources.tiffslide.tiffslide_metadata import OpenSlideLikeMetadata


class OpenSlideMetadata(OpenSlideLikeMetadata):
    def __init__(self, slide: OpenSlide):
        super().__init__(cast(TiffSlide, slide))

    @property
    def bounds_x_property_name(self) -> str:
        return PROPERTY_NAME_BOUNDS_X

    @property
    def bounds_y_property_name(self) -> str:
        return PROPERTY_NAME_BOUNDS_Y

    @property
    def mpp_x_property_name(self) -> str:
        return PROPERTY_NAME_MPP_X

    @property
    def mpp_y_property_name(self) -> str:
        return PROPERTY_NAME_MPP_Y

    @property
    def objective_power_property_name(self) -> str:
        return PROPERTY_NAME_OBJECTIVE_POWER

    @property
    def vendor_property_name(self) -> str:
        return PROPERTY_NAME_VENDOR
