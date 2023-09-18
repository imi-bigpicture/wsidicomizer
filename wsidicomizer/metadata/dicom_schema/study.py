from typing import Type
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    DateDicomField,
    DefaultingTagDicomField,
    PatientNameDicomField,
    TimeDicomField,
    UidDicomField,
)

from marshmallow import fields

from wsidicomizer.metadata.series import Series
from wsidicomizer.metadata.study import Study


class StudyDicomSchema(DicomSchema[Study]):
    """
    Type 1
    - uid
    Type 2
    - identifier
    - date
    - time
    - accession number
    - referring_physician_name
    """

    uid = DefaultingTagDicomField(
        UidDicomField(), tag="_uid", data_key="StudyInstanceUID"
    )
    identifier = fields.String(data_key="StudyID")
    date = DateDicomField(data_key="StudyDate")
    time = TimeDicomField(data_key="StudyTime")
    accession_number = fields.String(data_key="AccessionNumber")
    referring_physician_name = PatientNameDicomField(data_key="ReferringPhysicianName")

    @property
    def load_type(self) -> Type[Study]:
        return Study
