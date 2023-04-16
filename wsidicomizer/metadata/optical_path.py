from dataclasses import dataclass
from typing import Optional

from wsidicom.conceptcode import IlluminationCode, IlluminationColorCode

from wsidicomizer.metadata.base import DicomModelBase


@dataclass
class OpticalPath(DicomModelBase):
    optical_path_identifier: str
    illumination_type: IlluminationCode = IlluminationCode.from_code_meaning(
        "Brightfield illumination"
    )
    illumination_wave_length: Optional[float] = None
    illumination_color: Optional[IlluminationColorCode] = None
    icc_profile: Optional[bytes] = None
    objective_lens_power: Optional[float] = None

    @classmethod
    def create_brightfield_optical_path(
        cls,
        identifier: str = "0",
        magnification: Optional[float] = None,
        icc_profile: Optional[bytes] = None,
    ):
        return cls(
            identifier,
            IlluminationCode.from_code_meaning("Brightfield illumination"),
            illumination_color=IlluminationColorCode.from_code_meaning("Full Spectrum"),
            icc_profile=icc_profile,
            objective_lens_power=magnification,
        )
