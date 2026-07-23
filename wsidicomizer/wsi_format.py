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

"""WSI format enum with default image coordinate system values."""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from wsidicom.metadata import ImageCoordinateSystem, ImageType


class WsiFormat(Enum):
    """WSI format identifier."""

    SVS = "svs"
    NDPI = "ndpi"
    PHILIPS_TIFF = "philips_tiff"
    HISTECH_TIFF = "histech_tiff"
    OME_TIFF = "ome_tiff"
    MIRAX = "mirax"
    VENTANA = "ventana"
    CZI = "czi"
    ISYNTAX = "isyntax"
    GENERIC = "generic"


@dataclass(frozen=True)
class FormatCoordinateDefaults:
    """Default image coordinate system rotations for a WSI format.

    Vendor files often carry no image position, and frequently no rotation either. The
    rotation is, however, typically format-specific, so as a best effort each image is
    placed at the matching corner of a standard slide via
    :meth:`ImageCoordinateSystem.default_for`. The resulting origins are canonical slide
    corners, recognisable as defaults rather than measured positions.
    """

    level_rotation: float
    label_rotation: float | None
    overview_rotation: float | None

    ROTATIONS: ClassVar[dict[WsiFormat, tuple[float, float | None, float | None]]] = {
        WsiFormat.SVS: (180.0, 180.0, 180.0),
        WsiFormat.NDPI: (180.0, 180.0, 180.0),
        WsiFormat.PHILIPS_TIFF: (180.0, 180.0, 180.0),
        WsiFormat.HISTECH_TIFF: (0.0, None, None),
        WsiFormat.OME_TIFF: (0.0, None, None),
        WsiFormat.MIRAX: (270.0, 270.0, 270.0),
        WsiFormat.VENTANA: (0.0, None, None),
        WsiFormat.CZI: (0.0, None, None),
        WsiFormat.ISYNTAX: (180.0, 180.0, 180.0),
        WsiFormat.GENERIC: (0.0, None, None),
    }
    """Level, label and overview rotation for each WSI format."""

    @classmethod
    def from_wsi_format(cls, wsi_format: WsiFormat) -> "FormatCoordinateDefaults":
        """Return the default coordinate system rotations for a WSI format.

        Parameters
        ----------
        wsi_format: WsiFormat
            Format to return the defaults for.

        Returns
        -------
        FormatCoordinateDefaults
            The default coordinate system rotations for the format.
        """
        return cls(*cls.ROTATIONS[wsi_format])

    @classmethod
    def level_rotation_for(cls, wsi_format: WsiFormat) -> float:
        """Return the rotation of the level image of a WSI format.

        The rotation is a property of the format, and applies also to images placed
        from a position read from the file.

        Parameters
        ----------
        wsi_format: WsiFormat
            Format to return the level rotation for.

        Returns
        -------
        float
            The rotation of the level image in degrees.
        """
        return cls.from_wsi_format(wsi_format).level_rotation

    def level_coordinate_system(self) -> ImageCoordinateSystem:
        return ImageCoordinateSystem.default_for(self.level_rotation, ImageType.VOLUME)

    def label_coordinate_system(self) -> ImageCoordinateSystem | None:
        if self.label_rotation is None:
            return None
        return ImageCoordinateSystem.default_for(self.label_rotation, ImageType.LABEL)

    def overview_coordinate_system(self) -> ImageCoordinateSystem | None:
        if self.overview_rotation is None:
            return None
        return ImageCoordinateSystem.default_for(
            self.overview_rotation, ImageType.OVERVIEW
        )
