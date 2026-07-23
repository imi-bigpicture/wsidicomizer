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

from opentile import Metadata
from wsidicom.geometry import Orientation, PointMm, SizeMm
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


class OpenTileMetadata(WsiDicomizerMetadata):
    def __init__(
        self,
        metadata: Metadata,
        has_label: bool,
        has_overview: bool,
        icc_profile: bytes | None = None,
        wsi_format: WsiFormat | None = None,
        imaged_size: SizeMm | None = None,
    ):
        equipment = Equipment(
            metadata.scanner_manufacturer,
            metadata.scanner_model,
            metadata.scanner_serial_number,
            metadata.scanner_software_versions,
        )
        if wsi_format is not None:
            defaults = FormatCoordinateDefaults.from_wsi_format(wsi_format)
            image_coordinate_system = None
            if wsi_format == WsiFormat.NDPI and imaged_size is not None:
                image_coordinate_system = self._ndpi_level_coordinate_system(
                    metadata, imaged_size
                )
            if image_coordinate_system is None:
                image_coordinate_system = defaults.level_coordinate_system()
        else:
            defaults = None
            image_coordinate_system = None
        image = Image(
            metadata.acquisition_datetime,
            image_coordinate_system=image_coordinate_system,
        )
        objectives = (
            Objectives(objective_power=metadata.magnification)
            if metadata.magnification is not None
            else None
        )
        if objectives is not None or icc_profile is not None:
            optical_paths = [
                OpticalPath(
                    "1", objective=objectives, icc_profile=icc_profile
                ).add_color_space_from_icc()
            ]
        else:
            optical_paths = []
        pyramid = Pyramid(image=image, optical_paths=optical_paths)
        label_text = metadata.label_text
        if has_label or label_text is not None:
            label_image_coordinate_system = (
                defaults.label_coordinate_system() if defaults else None
            )
            label = Label(
                text=label_text,
                image=Image(
                    metadata.acquisition_datetime,
                    image_coordinate_system=label_image_coordinate_system,
                )
                if has_label
                else None,
                optical_paths=[],
            )
        else:
            label = None
        if has_overview:
            overview_image_coordinate_system = (
                defaults.overview_coordinate_system() if defaults else None
            )
            overview = Overview(
                image=Image(
                    metadata.acquisition_datetime,
                    image_coordinate_system=overview_image_coordinate_system,
                ),
                optical_paths=[],
            )
        else:
            overview = None
        super().__init__(
            equipment=equipment, pyramid=pyramid, label=label, overview=overview
        )

    @staticmethod
    def _ndpi_level_coordinate_system(
        metadata: Metadata, imaged_size: SizeMm
    ) -> ImageCoordinateSystem | None:
        """Return the level coordinate system measured from an ndpi file.

        Ndpi files store the offset from the center of the slide to the center of the
        imaged region, in nm along the image axes. Verified against the ndpi macro
        image, which covers the whole slide and has zero offset: x is along the image
        rows and y along the columns, both increasing in the stored image direction.

        Parameters
        ----------
        metadata: Metadata
            Metadata of the ndpi file.
        imaged_size: SizeMm
            Size of the imaged region of the level.

        Returns
        -------
        ImageCoordinateSystem | None
            The measured coordinate system, or `None` if the file does not carry the
            offsets.
        """
        rotation = FormatCoordinateDefaults.level_rotation_for(WsiFormat.NDPI)
        x = metadata.properties.get("x_offset_from_slide_center")
        y = metadata.properties.get("y_offset_from_slide_center")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        slide_size = ImageCoordinateSystem.SLIDE_SIZE_WITH_LABEL
        slide_middle = PointMm(slide_size.width / 2, slide_size.height / 2)
        offset = Orientation.from_rotation(rotation).apply_transform(
            PointMm(x / 10**6, y / 10**6)
        )
        return ImageCoordinateSystem.from_middle_of_slide(
            slide_middle + offset, imaged_size, rotation, None
        )
