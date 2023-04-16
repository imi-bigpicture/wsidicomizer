from dataclasses import dataclass, field
from typing import List

from wsidicomizer.metadata.base import DicomModelBase


@dataclass
class Equipment(DicomModelBase):
    manufacturer: str = "Unknown"
    manufacturer_model_name: str = "Unknown"
    device_serial_number: str = "Unknown"
    software_versions: List[str] = field(default_factory=lambda: ["Unknown"])
