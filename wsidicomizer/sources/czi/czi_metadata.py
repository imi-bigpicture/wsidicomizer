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

"""Metadata for czi file."""

import re
from collections.abc import Sequence
from datetime import datetime
from functools import cached_property
from typing import TypeVar
from xml.etree import ElementTree

import numpy as np
from czifile import CziFile
from wsidicom.geometry import SizeMm
from wsidicom.metadata import Equipment, Image, Objectives, OpticalPath, Pyramid

from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat

ElementType = TypeVar("ElementType", str, int, float)


class CziMetadata(WsiDicomizerMetadata):
    def __init__(self, czi: CziFile):
        metadata_xml = czi.metadata()
        if metadata_xml is None or not isinstance(metadata_xml, str):
            raise ValueError("No metadata string in file.")
        # CZI metadata XML comes from the local slide file, not untrusted network
        # input, so the stdlib parser is acceptable here.
        self._metadata = ElementTree.fromstring(metadata_xml)  # noqa: S314
        image = Image(
            acquisition_datetime=self.acquisition_datetime,
            pixel_spacing=self.pixel_spacing,
            image_coordinate_system=FormatCoordinateDefaults.from_wsi_format(
                WsiFormat.CZI
            ).level_coordinate_system(),
        )
        equipment = Equipment(
            model_name=self.scanner_model,
            software_versions=self.scanner_software_versions,
        )
        optical_paths = [
            OpticalPath("1", objective=Objectives(objective_power=self.magnification))
        ]
        pyramid = Pyramid(image=image, optical_paths=optical_paths)
        super().__init__(equipment=equipment, pyramid=pyramid)

    @property
    def acquisition_datetime(self) -> datetime | None:
        image = self.find_nested_element(["Metadata", "Information", "Image"])
        if image is None:
            return None
        element = image.find("AcquisitionDateAndTime")
        if element is None or element.text is None:
            return None
        try:
            return datetime.fromisoformat(element.text)
        except ValueError:
            pass
        # Remove timezone and keep only microseconds for Python <3.11 compatibility
        trimmed = re.split(r"Z|[-|+]\d{2}.\d{2}$", element.text)[0][:26]
        try:
            return datetime.fromisoformat(trimmed)
        except ValueError:
            return None

    @property
    def scanner_model(self) -> str | None:
        information = self.find_nested_element(["Metadata", "Information"])
        if information is None:
            return None
        reference = self.find_nested_element(["Image", "MicroscopeRef"], information)
        microscopes_element = self.find_nested_element(
            ["Instrument", "Microscopes"], information
        )
        if reference is None or microscopes_element is None:
            return None
        microscope_ref = reference.get("Id")
        microscopes = microscopes_element.findall("Microscope")
        try:
            microscope = next(
                microscope
                for microscope in microscopes
                if microscope.get("Id") == microscope_ref
            )
        except StopIteration:
            return None
        return microscope.get("Name")

    @property
    def magnification(self) -> float | None:
        information = self.find_nested_element(["Metadata", "Information"])
        if information is None:
            return None
        settings = self.find_nested_element(["Image", "ObjectiveSettings"], information)
        objectives_element = self.find_nested_element(
            ["Instrument", "Objectives"], information
        )
        if settings is None or objectives_element is None:
            return None
        objective_refs = [
            objective.get("Id") for objective in settings.findall("ObjectiveRef")
        ]
        if len(objective_refs) != 1:
            return None
        objectives = objectives_element.findall("Objective")
        try:
            objective = next(
                objective
                for objective in objectives
                if objective.get("Id") == objective_refs[0]
            )
        except StopIteration:
            return None
        try:
            return self.get_value_from_element(objective, "NominalMagnification", float)
        except ValueError:
            return None

    @property
    def scanner_software_versions(self) -> list[str] | None:
        application = self.find_nested_element(
            ["Metadata", "Information", "Application"]
        )
        if application is None:
            return None
        try:
            name = self.get_value_from_element(application, "Name", str)
            version = self.get_value_from_element(application, "Version", str)
        except ValueError:
            return None
        return [name + " " + version]

    @cached_property
    def scaling(self) -> tuple[float | None, float | None, float | None]:
        scaling_elements = self.find_nested_element(["Metadata", "Scaling", "Items"])
        if scaling_elements is None:
            return None, None, None
        x: float | None = None
        y: float | None = None
        z: float | None = None
        for distance in scaling_elements.findall("Distance"):
            dimension = distance.get("Id")
            # Value is in m per pixel, result in mm per pixel
            try:
                value = self.get_value_from_element(distance, "Value", float) * pow(
                    10, 6
                )
            except ValueError:
                continue
            if dimension == "X":
                x = value
            elif dimension == "Y":
                y = value
            elif dimension == "Z":
                z = value
        return x, y, z

    @cached_property
    def pixel_spacing(self) -> SizeMm | None:
        """Pixel spacing (mm per pixel) from the metadata, or None if the file
        does not state a readable one. The image data requires it and refuses to
        be created without."""
        x, y, _ = self.scaling
        if x is None or y is None:
            return None
        return SizeMm(x, y) / 1000

    @cached_property
    def focal_plane_mapping(self) -> list[float]:
        image = self.get_nested_element(["Metadata", "Information", "Image"])
        try:
            size_z = self.get_value_from_element(image, "SizeZ", int, 0)
            z_interval = self.get_nested_element(
                ["Dimensions", "Z", "Positions", "Interval"], image
            )
            start = self.get_value_from_element(z_interval, "Start", int)
            increment = self.get_value_from_element(z_interval, "Increment", int)
            _, _, z_scale = self.scaling
            if z_scale is None:
                raise ValueError("No z scale in metadata")
            start_z = start * z_scale
            end_z = (start + increment * size_z) * z_scale
            step_z = increment * z_scale
            return list(np.arange(start_z, end_z, step_z))  # type: ignore
        except ValueError:
            return [0.0]

    @cached_property
    def channel_mapping(self) -> list[str]:
        channels = self.get_nested_element(
            ["Metadata", "Information", "Image", "Dimensions", "Channels"]
        )
        return [
            self.get_value_from_element(channel, "Fluor", str) for channel in channels
        ]

    def find_nested_element(
        self, tags: Sequence[str], element: ElementTree.Element | None = None
    ) -> ElementTree.Element | None:
        """Return the nested element, or None if any tag along the way is absent.

        Metadata read from the file is optional as far as this class is
        concerned: what is not there is left unset rather than failing the open.
        """
        found_element = self._metadata if element is None else element
        for tag in tags:
            found_element = found_element.find(tag)
            if found_element is None:
                return None
        return found_element

    def get_nested_element(
        self, tags: Sequence[str], element: ElementTree.Element | None = None
    ) -> ElementTree.Element:
        if element is None:
            element = self._metadata
        found_element = element
        for tag in tags:
            found_element = found_element.find(tag)
            if found_element is None:
                raise ValueError(f"Tag {tag} not found in element")
        return found_element

    def get_value_from_element(
        self,
        element: ElementTree.Element,
        tag: str,
        value_type: type[ElementType],
        default: ElementType | None = None,
        nested: Sequence[str] | None = None,
    ) -> ElementType:
        if nested is not None:
            element = self.get_nested_element(nested, element)
        try:
            element = self.get_element(element, tag)
            text = element.text
            if text is None:
                raise ValueError("Text not found in element")
        except ValueError as exception:
            if default is not None:
                return default
            raise ValueError(f"Tag {tag} or text not found in element") from exception
        try:
            return value_type(text)
        except ValueError as exception:
            raise ValueError(
                f"Failed to convert tag {tag} value {text} to {value_type}."
            ) from exception

    @staticmethod
    def get_element(element: ElementTree.Element, tag: str) -> ElementTree.Element:
        found_element = element.find(tag)
        if found_element is None:
            raise ValueError(f"Tag {tag} not found in element")
        return found_element
