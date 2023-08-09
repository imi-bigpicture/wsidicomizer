from marshmallow import Schema, fields, post_load
from wsidicom.conceptcode import SpecimenStainsCode
from wsidicomizer.metadata.schema.fields import FieldFactory
from wsidicomizer.metadata.schema.sample import SlideSampleSchema, SpecimenSchema
from wsidicomizer.metadata.slide import Slide


class SlideSchema(Schema):
    identifier = fields.String(allow_none=True)
    stains = fields.List(
        FieldFactory.concept_code(SpecimenStainsCode)(), allow_none=True
    )
    samples = fields.Nested(SpecimenSchema, allow_none=True, many=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Slide(**data)
