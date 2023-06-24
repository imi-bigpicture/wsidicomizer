"""Image model."""
import datetime
from enum import Enum
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from pydicom import Dataset
from pydicom import Sequence as DicomSequence
from pydicom.valuerep import DSfloat
from wsidicom.geometry import PointMm
from wsidicom.instance import ImageType

from wsidicomizer.metadata.model_base import ModelBase
from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomBoolAttribute,
    DicomDateTimeAttribute,
    DicomNumberAttribute,
    DicomStringAttribute,
)


class FocusMethod(Enum):
    AUTO = "auto"
    MANUAL = "manual"


@dataclass
class ExtendedDepthOfField(ModelBase):
    number_of_focal_planes: int
    distance_between_focal_planes: float
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(
        self,
        dataset: Dataset,
        image_type: ImageType,
    ) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomNumberAttribute(
                "NumberOfFocalPlanes",
                True,
                self.number_of_focal_planes,
            ),
            DicomNumberAttribute(
                "DistanceBetweenFocalPlanes",
                True,
                self.distance_between_focal_planes,
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)


@dataclass
class ImageCoordinateSystem(ModelBase):
    origin: PointMm
    rotation: float
    overrides: Optional[Dict[str, bool]] = None

    @property
    def orientation(self) -> Tuple[float, float, float, float, float, float]:
        x = round(math.sin(self.rotation * math.pi / 180), 8)
        y = round(math.cos(self.rotation * math.pi / 180), 8)
        return tuple(DSfloat(value, True) for value in [-x, y, 0, y, x, 0])

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        origin_element = Dataset()
        origin_element.XOffsetInSlideCoordinateSystem = DSfloat(self.origin.x, True)
        origin_element.YOffsetInSlideCoordinateSystem = DSfloat(self.origin.y, True)
        dataset.TotalPixelMatrixOriginSequence = DicomSequence([origin_element])
        dataset.ImageOrientationSlide = list(self.orientation)


@dataclass
class Image(ModelBase):
    """
    Image metadata.

    Corresponds to the `Required, Empty if Unknown` attributes in the Slide Label
    module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.12.8.html
    """

    acquisition_datetime: Optional[datetime.datetime] = None
    focus_method: Optional[FocusMethod] = None
    extended_depth_of_field: Optional[ExtendedDepthOfField] = None
    image_coordinate_system: Optional[ImageCoordinateSystem] = None
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomDateTimeAttribute(
                "AcquisitionDateTime",
                True,
                self.acquisition_datetime,
                datetime.datetime(1, 1, 1),
            ),
            DicomStringAttribute(
                "FocusMethod",
                True,
                self.focus_method,
                "AUTO",
            ),
            DicomBoolAttribute(
                "ExtendedDepthOfField",
                True,
                self.extended_depth_of_field is not None,
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)
        if self.extended_depth_of_field is not None:
            self.extended_depth_of_field.insert_into_dataset(dataset, image_type)

        if self.image_coordinate_system is not None:
            self.image_coordinate_system.insert_into_dataset(dataset, image_type)
