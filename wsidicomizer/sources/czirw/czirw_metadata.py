#    Copyright 2026 SECTRA AB
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

"""Metadata for CZI files read by pylibCZIrw."""

from xml.etree import ElementTree

from wsidicom.metadata import Equipment, Image, Objectives, OpticalPath, Pyramid

from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.sources.czi.czi_metadata import CziMetadata
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat


class CziRwMetadata(CziMetadata):
    """CZI metadata populated from pylibCZIrw's raw XML metadata."""

    def __init__(self, raw_metadata: str, channel_count: int) -> None:
        # The XML is read from the local CZI file.
        self._metadata = ElementTree.fromstring(raw_metadata)  # noqa: S314
        image = Image(
            acquisition_datetime=self.acquisition_datetime,
            pixel_spacing=self.pixel_spacing,
            image_coordinate_system=FormatCoordinateDefaults.from_wsi_format(
                WsiFormat.CZI
            ).level_coordinate_system(),
        )
        magnification = self.magnification
        objective = (
            Objectives(objective_power=magnification)
            if magnification is not None
            else None
        )
        channel_names = self.channel_mapping
        optical_paths = [
            OpticalPath(
                str(index + 1),
                description=(
                    channel_names[index]
                    if index < len(channel_names) and channel_names[index]
                    else None
                ),
                objective=objective,
            )
            for index in range(channel_count)
        ]
        equipment = Equipment(
            manufacturer="ZEISS",
            model_name=self.scanner_model,
            software_versions=self.scanner_software_versions,
        )
        WsiDicomizerMetadata.__init__(
            self,
            study=self._study_started_at(self.acquisition_datetime),
            equipment=equipment,
            pyramid=Pyramid(image=image, optical_paths=optical_paths),
        )
