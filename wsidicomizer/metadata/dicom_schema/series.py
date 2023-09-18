from typing import Type
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    DefaultingDicomField,
    DefaultingTagDicomField,
    UidDicomField,
)

from marshmallow import fields

from wsidicomizer.metadata.series import Series


class SeriesDicomSchema(DicomSchema[Series]):
    """
    Type 1
    - uid
    - number
    """

    uid = DefaultingTagDicomField(
        UidDicomField(), tag="_uid", data_key="SeriesInstanceUID"
    )
    number = DefaultingDicomField(
        fields.Integer(), dump_default=1, data_key="SeriesNumber"
    )

    @property
    def load_type(self) -> Type[Series]:
        return Series
