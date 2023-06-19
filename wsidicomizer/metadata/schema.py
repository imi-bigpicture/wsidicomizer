from enum import Enum
from pydicom.uid import UID
from typing import Dict, Optional, Union
from marshmallow import (
    Schema,
    ValidationError,
    fields,
    pprint,
    post_load,
    pre_dump,
    pre_load,
    post_dump,
)
from pydicom.sr.coding import Code
from marshmallow_polyfield import PolyField


class UidField(fields.Field):
    def _serialize(self, value: Optional[UID], attr, obj, **kwargs) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def _deserialize(self, value, attr, data, **kwargs) -> UID:
        try:
            return UID(value)
        except ValueError as error:
            raise ValidationError("Could not deserialize UID.") from error


class CodeField(fields.Field):
    def _serialize(self, value: Optional[Code], attr, obj, **kwargs) -> Optional[Dict]:
        if value is None:
            return None
        return {
            "value": value.value,
            "scheme_designator": value.scheme_designator,
            "meaning": value.meaning,
            "scheme_version": value.scheme_version,
        }

    def _deserialize(self, value, attr, data, **kwargs) -> Code:
        try:
            return Code(**value)
        except ValueError as error:
            raise ValidationError("Could not deserialize Code.") from error


def str_or_code_serialization_scheme_selector(
    base_object: Union[str, Code], parent_object: object
):
    if isinstance(base_object, Code):
        return CodeField
    return fields.String


def str_or_code_deserialization_scheme_selector(
    object_dict: Dict, parent_object_dict: Dict
):
    code_attributes = ["value", "scheme_designator", "meaning"]
    if all(object_dict.get(attribute) for attribute in code_attributes):
        return CodeField
    return fields.String


class EquipmentSchema(Schema):
    manufacturer = fields.String(required=False)
    model_name = fields.String(required=False)
    device_serial_number = fields.String(required=False)
    software_versions = fields.List(fields.String(required=False))


class ExtendedDepthOfFieldSchema(Schema):
    number_of_focal_planes = fields.Integer()
    distance_between_focal_planes = fields.Float()


class PointMmSchema(Schema):
    x = fields.Integer()
    y = fields.Integer()


class ImageCoordinateSystemSchema(Schema):
    origin = fields.Nested(PointMmSchema)
    rotation = fields.Float()


class FocusMethod(Enum):
    AUTO = "auto"
    MANUAL = "manual"


class ImageSchema(Schema):
    acquisition_datetime = fields.DateTime(required=False)
    focus_method = fields.Enum(FocusMethod, by_value=False, required=False)
    extended_depth_of_field = fields.Nested(ExtendedDepthOfFieldSchema, required=False)
    image_coordinate_system = fields.Nested(ImageCoordinateSystemSchema, required=False)


class LabelSchema(Schema):
    label_text = fields.String(required=False)
    barcode_value = fields.String(required=False)
    label_in_volume_image = fields.Boolean(load_default=False)
    label_in_overview_image = fields.Boolean(load_default=False)
    label_is_phi = fields.Boolean(load_default=True)


class PatientDeIdentification(Schema):
    identity_removed = fields.Boolean(load_default=False)
    methods = fields.List(
        PolyField(
            serialization_schema_selector=str_or_code_serialization_scheme_selector,
            deserialization_schema_selector=str_or_code_deserialization_scheme_selector,
            required=False,
        )
    )


class PatientSex(Enum):
    F = "female"
    M = "male"
    O = "other"


class PatientSchema(Schema):
    name = fields.String(required=False)
    identifier = fields.String(required=False)
    birth_date = fields.DateTime(required=False)
    sex = fields.Enum(PatientSex, by_value=False, required=False)
    species_description = PolyField(
        serialization_schema_selector=str_or_code_serialization_scheme_selector,
        deserialization_schema_selector=str_or_code_deserialization_scheme_selector,
        required=False,
    )
    de_identification: Optional[PatientDeIdentification] = None


class SeriesSchema(Schema):
    uid = UidField(required=False)
    number = fields.Integer(required=False)


class StudySchema(Schema):
    uid = UidField(required=False)
    identifier = fields.String(required=False)
    date = fields.Date(required=False)
    time = fields.Time(required=False)
    accession_number = fields.String(required=False)
    referring_physician_name = fields.String(required=False)
