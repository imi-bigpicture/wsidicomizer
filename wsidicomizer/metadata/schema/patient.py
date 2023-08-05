from marshmallow import Schema, fields, post_load
from wsidicomizer.metadata.patient import Patient, PatientDeIdentification, PatientSex
from wsidicomizer.metadata.schema.fields import FieldFactory, StringOrCodeField


class PatientDeIdentificationSchema(Schema):
    identity_removed = fields.Boolean(load_default=False)
    methods = fields.List(StringOrCodeField(), allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return PatientDeIdentification(**data)


class PatientSchema(Schema):
    name = fields.String(allow_none=True)
    identifier = fields.String(allow_none=True)
    birth_date = fields.Date(allow_none=True)
    sex = fields.Enum(PatientSex, by_value=True, allow_none=True)
    species_description = StringOrCodeField(allow_none=True)
    de_identification = fields.Nested(PatientDeIdentificationSchema(), allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Patient(**data)
