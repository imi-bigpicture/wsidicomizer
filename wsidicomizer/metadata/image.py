"""Image model."""
import datetime
from enum import Enum
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydicom import Dataset
from pydicom import Sequence as DicomSequence
from pydicom.valuerep import DSfloat
from wsidicom.geometry import PointMm, Orientation
from wsidicom.instance import ImageType
from wsidicomizer.metadata.defaults import defaults

from wsidicomizer.metadata.base_model import BaseModel
from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomBoolAttribute,
    DicomDateTimeAttribute,
    DicomNumericAttribute,
    DicomStringAttribute,
)


class FocusMethod(Enum):
    AUTO = "auto"
    MANUAL = "manual"


@dataclass
class ExtendedDepthOfField(BaseModel):
    number_of_focal_planes: int
    distance_between_focal_planes: float

    def insert_into_dataset(
        self,
        dataset: Dataset,
        image_type: ImageType,
    ) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomNumericAttribute(
                "NumberOfFocalPlanes",
                True,
                self.number_of_focal_planes,
            ),
            DicomNumericAttribute(
                "DistanceBetweenFocalPlanes",
                True,
                self.distance_between_focal_planes,
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)


@dataclass
class ImageCoordinateSystem(BaseModel):
    origin: PointMm
    rotation: float

    @property
    def orientation(self) -> Orientation:
        x = round(math.sin(self.rotation * math.pi / 180), 8)
        y = round(math.cos(self.rotation * math.pi / 180), 8)
        return Orientation([-x, y, 0, y, x, 0])

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        origin_element = Dataset()
        origin_element.XOffsetInSlideCoordinateSystem = DSfloat(self.origin.x, True)
        origin_element.YOffsetInSlideCoordinateSystem = DSfloat(self.origin.y, True)
        dataset.TotalPixelMatrixOriginSequence = DicomSequence([origin_element])
        dataset.ImageOrientationSlide = list(
            DSfloat(value, True) for value in self.orientation.values
        )


@dataclass
class Image(BaseModel):
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

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomDateTimeAttribute(
                "AcquisitionDateTime",
                True,
                self.acquisition_datetime,
                defaults.date_time,
            ),
            DicomStringAttribute(
                "FocusMethod",
                True,
                self.focus_method,
                defaults.focus_method,
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
