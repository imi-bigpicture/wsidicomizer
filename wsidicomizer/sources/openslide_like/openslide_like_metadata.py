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
from collections.abc import Mapping
from dataclasses import dataclass, field

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
    Series,
    Slide,
)

from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.sources.openslide_like.openslide_like_vendor_metadata import (
    VendorMetadata,
)
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat

logger = logging.getLogger(__name__)


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
    barcode: str | None = None
    raw_properties: Mapping[str, str] = field(default_factory=dict)
    """All properties, for reading vendor-specific keys openslide does not
    normalise (e.g. ``mirax.GENERAL.SLIDE_NAME``, ``philips.DICOM_*``)."""

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


def _parse_float(value: str | None) -> float | None:
    """Return value as a float, or None when absent or not a number.

    openslide-like properties are strings read from the file, so a malformed one
    cannot be told apart from a missing one here. It is for the caller to decide
    whether that is something to leave out or to refuse to convert without.
    """
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class OpenSlideLikeMetadata(WsiDicomizerMetadata):
    def __init__(
        self,
        properties: OpenSlideLikeProperties,
        color_profile: ImageCmsProfile | None,
    ):
        vendor_metadata = VendorMetadata.for_vendor(
            properties.vendor, properties.raw_properties
        )
        equipment = Equipment(
            manufacturer=vendor_metadata.manufacturer or properties.vendor,
            model_name=vendor_metadata.model_name,
            device_serial_number=vendor_metadata.device_serial_number,
            software_versions=vendor_metadata.software_versions,
        )
        series = Series(description=vendor_metadata.series_description)
        slide = Slide(identifier=vendor_metadata.container_identifier)
        if properties.mpp_x is None or properties.mpp_y is None:
            logger.warning("The file did not provide mpp, so pixel spacing is unknown.")
            pixel_spacing = None
        else:
            base_mpp_x = _parse_float(properties.mpp_x)
            base_mpp_y = _parse_float(properties.mpp_y)
            if base_mpp_x is None or base_mpp_y is None:
                logger.warning(
                    "Could not read mpp %r/%r from the file as a number, "
                    "so pixel spacing is unknown.",
                    properties.mpp_x,
                    properties.mpp_y,
                )
                pixel_spacing = None
            else:
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
        bounds_x = _parse_float(properties.bounds_x)
        bounds_y = _parse_float(properties.bounds_y)
        if bounds_x is not None and bounds_y is not None and pixel_spacing is not None:
            origin = PointMm(
                bounds_x * pixel_spacing.width,
                bounds_y * pixel_spacing.height,
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
            pixel_spacing=pixel_spacing,
            image_coordinate_system=image_coordinate_system,
            acquisition_datetime=vendor_metadata.acquisition_datetime,
        )
        objective_power = _parse_float(properties.objective_power)
        objectives = (
            Objectives(
                objective_power=objective_power,
                objective_numerical_aperture=(
                    vendor_metadata.objective_numerical_aperture
                ),
            )
            if objective_power is not None
            or vendor_metadata.objective_numerical_aperture is not None
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
        label_image_coordinate_system = (
            defaults.label_coordinate_system() if defaults is not None else None
        )
        if properties.barcode is not None or label_image_coordinate_system is not None:
            label = Label(
                barcode=properties.barcode,
                image=Image(image_coordinate_system=label_image_coordinate_system),
            )
        if defaults is not None:
            overview_image_coordinate_system = defaults.overview_coordinate_system()
            if overview_image_coordinate_system is not None:
                overview = Overview(
                    image=Image(
                        image_coordinate_system=overview_image_coordinate_system
                    ),
                    optical_paths=[],
                )
        super().__init__(
            series=series,
            slide=slide,
            equipment=equipment,
            pyramid=pyramid,
            label=label,
            overview=overview,
        )
