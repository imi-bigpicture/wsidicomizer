from marshmallow import Schema, fields, post_load

from wsidicomizer.metadata.schema.fields import UidField
from wsidicomizer.metadata.study import Study


class StudySchema(Schema):
    uid = UidField(allow_none=True)
    identifier = fields.String(allow_none=True)
    date = fields.Date(allow_none=True)
    time = fields.Time(allow_none=True)
    accession_number = fields.String(allow_none=True)
    referring_physician_name = fields.String(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Study(**data)
