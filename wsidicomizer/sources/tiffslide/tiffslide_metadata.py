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

import logging
from abc import abstractmethod

from tiffslide import TiffSlide
from tiffslide.tiffslide import (
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    PROPERTY_NAME_MPP_X,
    PROPERTY_NAME_MPP_Y,
    PROPERTY_NAME_OBJECTIVE_POWER,
    PROPERTY_NAME_VENDOR,
)
from wsidicom.geometry import PointMm, SizeMm
from wsidicom.metadata import (
    Equipment,
    Image,
    ImageCoordinateSystem,
    Objectives,
    OpticalPath,
)

from wsidicomizer.metadata import WsiDicomizerMetadata


class OpenSlideLikeMetadata(WsiDicomizerMetadata):
    @property
    @abstractmethod
    def bounds_x_property_name(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def bounds_y_property_name(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def mpp_x_property_name(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def mpp_y_property_name(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def objective_power_property_name(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def vendor_property_name(self) -> str:
        raise NotImplementedError()

    def __init__(self, slide: TiffSlide):
        magnification = slide.properties.get(self.objective_power_property_name)
        if magnification is not None:
            OpticalPath("0", objective=Objectives(objective_power=float(magnification)))
        equipment = Equipment(
            manufacturer=slide.properties.get(self.vendor_property_name)
        )
        try:
            base_mpp_x = float(slide.properties[self.mpp_x_property_name])
            base_mpp_y = float(slide.properties[self.mpp_y_property_name])
            pixel_spacing = SizeMm(
                base_mpp_x / 1000.0,
                base_mpp_y / 1000.0,
            )
        except (KeyError, TypeError):
            logging.warning(
                f"Could not determine pixel spacing as {slide} did not "
                "provide mpp from the file.",
                exc_info=True,
            )
            pixel_spacing = None
        # Get set image origin and size to bounds if available
        bounds_x = slide.properties.get(self.bounds_x_property_name, None)
        bounds_y = slide.properties.get(self.bounds_y_property_name, None)
        if bounds_x is not None and bounds_y is not None and pixel_spacing is not None:
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
        if slide.color_profile is not None:
            optical_path = OpticalPath(icc_profile=slide.color_profile.tobytes())
            optical_paths = [optical_path]
        else:
            optical_paths = None
        super().__init__(equipment=equipment, image=image, optical_paths=optical_paths)


class TiffSlideMetadata(OpenSlideLikeMetadata):
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
