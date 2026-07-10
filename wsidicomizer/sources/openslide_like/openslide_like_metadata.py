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

from PIL.ImageCms import ImageCmsProfile
from wsidicom.geometry import PointMm, SizeMm
from wsidicom.metadata import (
    Equipment,
    Image,
    ImageCoordinateSystem,
    Label,
    Objectives,
    OpticalPath,
    Overview,
    Pyramid,
)

from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat


@dataclass
class OpenSlideLikeProperties:
    background_color: str | None = None
    bounds_x: str | None = None
    bounds_y: str | None = None
    bounds_width: str | None = None
    bounds_height: str | None = None
    objective_power: str | None = None
    vendor: str | None = None
    mpp_x: str | None = None
    mpp_y: str | None = None

    @property
    def wsi_format(self) -> WsiFormat | None:
        """Return the WsiFormat for the vendor, if recognised."""
        if self.vendor is None:
            return None
        vendor_map: dict[str, WsiFormat] = {
            "aperio": WsiFormat.SVS,
            "hamamatsu": WsiFormat.NDPI,
            "mirax": WsiFormat.MIRAX,
            "ventana": WsiFormat.VENTANA,
            "philips": WsiFormat.PHILIPS_TIFF,
        }
        return vendor_map.get(self.vendor.lower())


class OpenSlideLikeMetadata(WsiDicomizerMetadata):
    def __init__(
        self,
        properties: OpenSlideLikeProperties,
        color_profile: ImageCmsProfile | None,
    ):
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
        wsi_format = properties.wsi_format
        defaults = (
            FormatCoordinateDefaults.from_wsi_format(wsi_format) if wsi_format else None
        )
        rotation = defaults.level_rotation if defaults else 0
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
                rotation,
            )
        else:
            if defaults is not None:
                image_coordinate_system = defaults.level_coordinate_system()
            else:
                image_coordinate_system = None
        image = Image(
            pixel_spacing=pixel_spacing, image_coordinate_system=image_coordinate_system
        )
        objectives = (
            Objectives(objective_power=float(properties.objective_power))
            if properties.objective_power is not None
            else None
        )
        icc_profile = color_profile.tobytes() if color_profile is not None else None
        if objectives is not None or icc_profile is not None:
            optical_paths = [
                OpticalPath(
                    "1", objective=objectives, icc_profile=icc_profile
                ).add_color_space_from_icc()
            ]
        else:
            optical_paths = []
        pyramid = Pyramid(image=image, optical_paths=optical_paths)

        label = None
        overview = None
        if defaults is not None:
            label_image_coordinate_system = defaults.label_coordinate_system()
            if label_image_coordinate_system is not None:
                label = Label(
                    image=Image(image_coordinate_system=label_image_coordinate_system)
                )
            overview_image_coordinate_system = defaults.overview_coordinate_system()
            if overview_image_coordinate_system is not None:
                overview = Overview(
                    image=Image(
                        image_coordinate_system=overview_image_coordinate_system
                    ),
                    optical_paths=[],
                )
        super().__init__(
            equipment=equipment, pyramid=pyramid, label=label, overview=overview
        )
