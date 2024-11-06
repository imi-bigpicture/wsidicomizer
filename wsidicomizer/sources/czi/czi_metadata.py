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
from datetime import datetime
from functools import cached_property
from typing import List, Optional, Sequence, Tuple, Type, TypeVar
from xml.etree import ElementTree

import numpy as np
from czifile import CziFile
from wsidicom.geometry import SizeMm
from wsidicom.metadata import Equipment, Image, Objectives, OpticalPath

from wsidicomizer.metadata import WsiDicomizerMetadata

ElementType = TypeVar("ElementType", str, int, float)


class CziMetadata(WsiDicomizerMetadata):
    def __init__(self, czi: CziFile):
        metadata_xml = czi.metadata()
        if metadata_xml is None or not isinstance(metadata_xml, str):
            raise ValueError("No metadata string in file.")
        self._metadata = ElementTree.fromstring(metadata_xml)
        image = Image(
            acquisition_datetime=self.aquisition_datetime,
            pixel_spacing=self.pixel_spacing,
        )
        equipment = Equipment(
            model_name=self.scanner_model,
            software_versions=self.scanner_software_versions,
        )
        optical_paths = [
            OpticalPath("0", objective=Objectives(objective_power=self.magnification))
        ]
        super().__init__(equipment=equipment, image=image, optical_paths=optical_paths)

    @property
    def aquisition_datetime(self) -> Optional[datetime]:
        value = self.get_value_from_element(
            self._metadata,
            "AcquisitionDateAndTime",
            str,
            nested=["Metadata", "Information", "Image"],
        )
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            # Remove timezone and keep only microseconds for Python <3.11 compatibility
            value = re.split(r"Z|[-|+]\d{2}.\d{2}$", value)[0][:26]
            return datetime.fromisoformat(value)

    @property
    def scanner_model(self) -> Optional[str]:
        information = self.get_nested_element(["Metadata", "Information"])
        image = self.get_nested_element(["Image"], information)
        microscope_ref = self.get_element(image, "MicroscopeRef").get("Id")
        microscopes = self.get_nested_element(
            ["Instrument", "Microscopes"], information
        ).findall("Microscope")
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
    def magnification(self) -> Optional[float]:
        information = self.get_nested_element(["Metadata", "Information"])
        objective_refs = [
            objective.get("Id")
            for objective in self.get_nested_element(
                ["Image", "ObjectiveSettings"], information
            ).findall("ObjectiveRef")
        ]
        if len(objective_refs) != 1:
            return None
        objectives = self.get_nested_element(
            ["Instrument", "Objectives"], information
        ).findall("Objective")
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
    def scanner_software_versions(self) -> Optional[List[str]]:
        application = self.get_nested_element(
            ["Metadata", "Information", "Application"]
        )
        try:
            name = self.get_value_from_element(application, "Name", str)
            version = self.get_value_from_element(application, "Version", str)
        except ValueError:
            return None
        return [name + " " + version]

    @cached_property
    def scaling(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        scaling_elements = self.get_nested_element(["Metadata", "Scaling", "Items"])
        x: Optional[float] = None
        y: Optional[float] = None
        z: Optional[float] = None
        for distance in scaling_elements.findall("Distance"):
            dimension = distance.get("Id")
            # Value is in m per pixel, result in mm per pixel
            value = self.get_value_from_element(
                distance,
                "Value",
                float,
            ) * pow(10, 6)
            if dimension == "X":
                x = value
            elif dimension == "Y":
                y = value
            elif dimension == "Z":
                z = value
        return x, y, z

    @cached_property
    def pixel_spacing(self) -> SizeMm:
        """Get pixel spacing (mm per pixel) from metadata"""
        x, y, _ = self.scaling
        if x is None or y is None:
            raise ValueError("Could not find pixel spacing in metadata")
        return SizeMm(x, y) / 1000

    @cached_property
    def focal_plane_mapping(self) -> List[float]:
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
            return list(np.arange(start_z, end_z, step_z))
        except ValueError:
            return [0.0]

    @cached_property
    def channel_mapping(self) -> List[str]:
        channels = self.get_nested_element(
            ["Metadata", "Information", "Image", "Dimensions", "Channels"]
        )
        return [
            self.get_value_from_element(channel, "Fluor", str) for channel in channels
        ]

    def get_nested_element(
        self, tags: Sequence[str], element: Optional[ElementTree.Element] = None
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
        value_type: Type[ElementType],
        default: Optional[ElementType] = None,
        nested: Optional[Sequence[str]] = None,
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
