#    Copyright 2025 SECTRA AB
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

"""Metadata for openslide like file."""

import logging
from dataclasses import dataclass
from typing import Optional

from PIL.ImageCms import ImageCmsProfile
from wsidicom.geometry import PointMm, SizeMm
from wsidicom.metadata import (
    Equipment,
    Image,
    ImageCoordinateSystem,
    Objectives,
    OpticalPath,
)

from wsidicomizer.metadata import WsiDicomizerMetadata


@dataclass
class OpenSlideLikeProperties:
    background_color: Optional[str] = None
    bounds_x: Optional[str] = None
    bounds_y: Optional[str] = None
    bounds_width: Optional[str] = None
    bounds_height: Optional[str] = None
    objective_power: Optional[str] = None
    vendor: Optional[str] = None
    mpp_x: Optional[str] = None
    mpp_y: Optional[str] = None


class OpenSlideLikeMetadata(WsiDicomizerMetadata):
    def __init__(
        self,
        properties: OpenSlideLikeProperties,
        color_profile: Optional[ImageCmsProfile],
    ):
        if properties.objective_power is not None:
            OpticalPath(
                "0",
                objective=Objectives(objective_power=float(properties.objective_power)),
            )
        equipment = Equipment(manufacturer=properties.vendor)
        if properties.mpp_x is None or properties.mpp_y is None:
            logging.warning(
                "Could not determine pixel spacing as did not "
                "provide mpp from the file.",
                exc_info=True,
            )
            pixel_spacing = None
        else:
            base_mpp_x = float(properties.mpp_x)
            base_mpp_y = float(properties.mpp_y)
            pixel_spacing = SizeMm(
                base_mpp_x / 1000.0,
                base_mpp_y / 1000.0,
            )

        # Get set image origin and size to bounds if available
        if (
            properties.bounds_x is not None
            and properties.bounds_y is not None
            and pixel_spacing is not None
        ):
            origin = PointMm(
                int(properties.bounds_x) * pixel_spacing.width,
                int(properties.bounds_y) * pixel_spacing.height,
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
        if color_profile is not None:
            optical_path = OpticalPath(icc_profile=color_profile.tobytes())
            optical_paths = [optical_path]
        else:
            optical_paths = None
        super().__init__(equipment=equipment, image=image, optical_paths=optical_paths)
