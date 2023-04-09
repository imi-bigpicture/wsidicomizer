from dataclasses import dataclass
from typing import Optional

from wsidicomizer.model.base import DicomModelBase


@dataclass
class Label(DicomModelBase):
    """Required if label image type."""

    label_text: Optional[str] = None
    barcode_value: Optional[str] = None
