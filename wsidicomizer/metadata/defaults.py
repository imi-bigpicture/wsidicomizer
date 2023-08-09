import datetime
from dataclasses import dataclass

from wsidicom.conceptcode import (
    ContainerComponentTypeCode,
    ContainerTypeCode,
    IlluminationCode,
    IlluminationColorCode,
)


@dataclass
class Defaults:
    string = "Unknown"
    date_time = datetime.datetime(1, 1, 1)
    illumination_type = IlluminationCode("Brightfield illumination").code
    illumination = IlluminationColorCode("Full Spectrum").code
    slide_container_type = ContainerTypeCode("Microscope slide").code
    slide_component_type = ContainerComponentTypeCode(
        "Microscope slide cover slip"
    ).code
    slide_material = "GLASS"
    focus_method = "AUTO"


defaults = Defaults()
