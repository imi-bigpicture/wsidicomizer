from marshmallow import Schema, fields, post_load

from wsidicomizer.metadata.schema.fields import UidField
from wsidicomizer.metadata.series import Series


class SeriesSchema(Schema):
    uid = UidField(allow_none=True)
    number = fields.Integer(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Series(**data)
