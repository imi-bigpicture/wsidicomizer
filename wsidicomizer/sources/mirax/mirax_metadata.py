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

"""DICOM metadata for a MIRAX slide, built from its `Slidedat`."""

from wsidicom.geometry import Point, PointMm, SizeMm
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
from wsidicomizer.sources.mirax.reader.slidedat import Slidedat
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat

_MANUFACTURER = "3DHISTECH"


class MiraxMetadata(WsiDicomizerMetadata):
    """Metadata for a MIRAX slide, built from its `Slidedat`: pixel spacing,
    objective and coordinate systems, plus the scanner manufacturer, acquisition
    datetime and software version."""

    def __init__(self, slidedat: Slidedat, bounds_offset: Point):
        """Build DICOM metadata from a slide's `Slidedat`.

        Parameters
        ----------
        slidedat: Slidedat
            The slide's settings and scanner metadata.
        bounds_offset: Point
            Level-0 pixel position of the read tissue bounding box in the slide's
            scan coordinates, placing the image origin as openslide's bounds do.
        """
        defaults = FormatCoordinateDefaults.from_wsi_format(WsiFormat.MIRAX)
        mpp = slidedat.mpp
        pixel_spacing = SizeMm(mpp[0] / 1000.0, mpp[1] / 1000.0) if mpp else None
        if pixel_spacing is not None:
            image_coordinate_system = ImageCoordinateSystem(
                PointMm(
                    bounds_offset.x * pixel_spacing.width,
                    bounds_offset.y * pixel_spacing.height,
                ),
                defaults.level_rotation,
            )
        else:
            image_coordinate_system = defaults.level_coordinate_system()

        equipment = Equipment(
            manufacturer=_MANUFACTURER,
            model_name=slidedat.scanner_hardware_version,
            device_serial_number=slidedat.scanner_hardware_id,
            software_versions=slidedat.software_versions,
        )
        series = Series(description=slidedat.slide_name)
        slide = Slide(identifier=slidedat.slide_id)
        image = Image(
            acquisition_datetime=slidedat.acquisition_datetime,
            pixel_spacing=pixel_spacing,
            image_coordinate_system=image_coordinate_system,
        )
        objective_power = slidedat.objective_power
        objectives = (
            Objectives(objective_power=objective_power)
            if objective_power is not None
            else None
        )
        # fluorescence: one optical path per channel (identified by fluorophore
        # name, matching MiraxFluorescenceLevelImageData.optical_paths)
        channels = slidedat.channels
        if channels:
            optical_paths = [
                OpticalPath(channel.name, objective=objectives) for channel in channels
            ]
        elif objectives is not None:
            optical_paths = [OpticalPath("1", objective=objectives)]
        else:
            optical_paths = []
        pyramid = Pyramid(image=image, optical_paths=optical_paths)

        label = None
        label_coordinate_system = defaults.label_coordinate_system()
        if label_coordinate_system is not None:
            label = Label(image=Image(image_coordinate_system=label_coordinate_system))
        overview = None
        overview_coordinate_system = defaults.overview_coordinate_system()
        if overview_coordinate_system is not None:
            overview = Overview(
                image=Image(image_coordinate_system=overview_coordinate_system),
                optical_paths=[],
            )
        super().__init__(
            series=series,
            equipment=equipment,
            slide=slide,
            pyramid=pyramid,
            label=label,
            overview=overview,
        )
