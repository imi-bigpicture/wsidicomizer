import datetime
import math
from typing import Literal, Optional, Tuple

from pydicom import Dataset
from pydicom import Sequence as DicomSequence
from pydicom.valuerep import DSfloat
from wsidicom.geometry import PointMm
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base import (
    DicomDateTimeAttribute,
    DicomModelBase,
    DicomNumberAttribute,
    DicomStringAttribute,
)


class ExtendedDepthOfField(DicomModelBase):
    def __init__(
        self, number_of_focal_planes: int, distance_between_focal_planes: float
    ):
        self._number_of_focal_planes = DicomNumberAttribute(
            "NumberOfFocalPlanes", True, number_of_focal_planes
        )
        self._distance_between_focal_planes = DicomNumberAttribute(
            "DistanceBetweenFocalPlanes", True, distance_between_focal_planes
        )
        self._dicom_attributes = [
            self._number_of_focal_planes,
            self._distance_between_focal_planes,
        ]

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        self._insert_dicom_attributes_into_dataset(dataset)


class ImageCoordinateSystem(DicomModelBase):
    def __init__(self, origin: PointMm, rotation: float):
        self._origin = origin
        self._rotation = rotation

    @property
    def origin(self) -> PointMm:
        return self._origin

    @property
    def rotation(self) -> float:
        return self._rotation

    @property
    def orientation(self) -> Tuple[float, float, float, float, float, float]:
        x = round(math.sin(self._rotation * math.pi / 180), 8)
        y = round(math.cos(self._rotation * math.pi / 180), 8)
        return tuple(DSfloat(value, True) for value in [-x, y, 0, y, x, 0])

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        origin_element = Dataset()
        origin_element.XOffsetInSlideCoordinateSystem = DSfloat(self._origin.x, True)
        origin_element.YOffsetInSlideCoordinateSystem = DSfloat(self._origin.y, True)
        dataset.TotalPixelMatrixOriginSequence = DicomSequence([origin_element])
        dataset.ImageOrientationSlide = list(self.orientation)


class Image(DicomModelBase):
    """
    Image metadata.

    Corresponds to the `Required, Empty if Unknown` attributes in the Slide Label
    module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.12.8.html
    """

    def __init__(
        self,
        acquisition_datetime: Optional[datetime.datetime],
        focus_method: Optional[Literal["AUTO", "MANUAL"]] = None,
        extended_depth_of_field: Optional[ExtendedDepthOfField] = None,
        image_coordinate_system: Optional[ImageCoordinateSystem] = None,
    ):
        self._acquisition_datetime = DicomDateTimeAttribute(
            "AcquisitionDateTime",
            True,
            acquisition_datetime,
            self._default_datetime_value,
            self._format_datetime_value,
        )
        self._focus_method = DicomStringAttribute(
            "FocusMethod", True, focus_method, lambda: "AUTO"
        )
        self._extended_depth_of_field = extended_depth_of_field
        self._image_coordinate_system = image_coordinate_system
        self._dicom_attributes = [self._acquisition_datetime, self._focus_method]

    @property
    def image_coordinate_system(self) -> Optional[ImageCoordinateSystem]:
        return self._image_coordinate_system

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        self._insert_dicom_attributes_into_dataset(dataset)
        if self._extended_depth_of_field is None:
            self.ExtendedDepthOfField = self._bool_to_literal(False)
        else:
            self.ExtendedDepthOfField = self._bool_to_literal(True)
            self._extended_depth_of_field.insert_into_dataset(dataset, image_type)
        if self._image_coordinate_system is not None:
            self._image_coordinate_system.insert_into_dataset(dataset, image_type)
