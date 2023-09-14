from marshmallow import Schema, fields, post_load
from wsidicomizer.metadata.schema.sample import (
    SpecimenSchema,
    StainingSchema,
)
from wsidicomizer.metadata.slide import Slide


class SlideSchema(Schema):
    identifier = fields.String(allow_none=True)
    stainings = fields.List(fields.Nested(StainingSchema()), allow_none=True)
    samples = fields.Nested(SpecimenSchema(), allow_none=True, many=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Slide(**data)
