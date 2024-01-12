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

import logging

from wsidicom.geometry import PointMm, SizeMm
from wsidicom.metadata import (
    Equipment,
    Image,
    ImageCoordinateSystem,
    Objectives,
    OpticalPath,
)

from wsidicomizer.extras.openslide.openslide import (
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    PROPERTY_NAME_MPP_X,
    PROPERTY_NAME_MPP_Y,
    PROPERTY_NAME_OBJECTIVE_POWER,
    PROPERTY_NAME_VENDOR,
    OpenSlide,
)
from wsidicomizer.metadata import WsiDicomizerMetadata


class OpenSlideMetadata(WsiDicomizerMetadata):
    def __init__(self, slide: OpenSlide):
        magnification = slide.properties.get(PROPERTY_NAME_OBJECTIVE_POWER)
        if magnification is not None:
            OpticalPath("0", objective=Objectives(objective_power=float(magnification)))
        equipment = Equipment(manufacturer=slide.properties.get(PROPERTY_NAME_VENDOR))
        try:
            base_mpp_x = float(slide.properties[PROPERTY_NAME_MPP_X])
            base_mpp_y = float(slide.properties[PROPERTY_NAME_MPP_Y])
            pixel_spacing = SizeMm(
                base_mpp_x / 1000.0,
                base_mpp_y / 1000.0,
            )
        except (KeyError, TypeError):
            logging.warning(
                "Could not determine pixel spacing as tiffslide did not "
                "provide mpp from the file.",
                exc_info=True,
            )
            pixel_spacing = None
        # Get set image origin and size to bounds if available
        bounds_x = slide.properties.get(PROPERTY_NAME_BOUNDS_X, 0)
        bounds_y = slide.properties.get(PROPERTY_NAME_BOUNDS_Y, 0)
        if pixel_spacing is not None:
            origin = PointMm(
                int(bounds_x) * pixel_spacing.width,
                int(bounds_y) * pixel_spacing.height,
            )
            image_coordinate_system = ImageCoordinateSystem(
                origin,
                0,
            )
        else:
            image_coordinate_system = None
        image = Image(
            pixel_spacing=pixel_spacing, image_coordinate_system=image_coordinate_system
        )
        super().__init__(equipment=equipment, image=image)
