from marshmallow import Schema, fields, post_load
from wsidicom.conceptcode import (
    ImagePathFilterCode,
    LightPathFilterCode,
    LenseCode,
    IlluminationCode,
    IlluminationColorCode,
)
from wsidicomizer.metadata.optical_path import (
    ImagePathFilter,
    Objectives,
    LightPathFilter,
    OpticalPath,
)

from wsidicomizer.metadata.schema.fields import FieldFactory


class LightPathFilterSchema(Schema):
    filters = fields.List(FieldFactory.concept_code(LightPathFilterCode)())
    nominal = fields.Float(allow_none=True)
    low_pass = fields.Float(allow_none=True)
    high_pass = fields.Float(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return LightPathFilter(**data)


class ImagePathFilterSchema(Schema):
    filters = fields.List(FieldFactory.concept_code(ImagePathFilterCode)())
    nominal = fields.Float(allow_none=True)
    low_pass = fields.Float(allow_none=True)
    high_pass = fields.Float(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return ImagePathFilter(**data)


class ObjectivesSchema(Schema):
    """Set of lens conditions for optical path"""

    lenses = fields.List(FieldFactory.concept_code(LenseCode))
    condenser_power = fields.Float(allow_none=True)
    objective_power = fields.Float(allow_none=True)
    objective_numerical_aperature = fields.Float(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Objectives(**data)


class OpticalPathSchema(Schema):
    identifier = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    illumination_type = FieldFactory.concept_code(IlluminationCode)(allow_none=True)
    illumination = FieldFactory.float_or_concept_code(IlluminationColorCode)(
        allow_none=True
    )
    # icc_profile: Optional[bytes] = None
    # lut: Optional[Lut] = None
    light_path_filter = fields.Nested(LightPathFilterSchema(), allow_none=True)
    image_path_filter = fields.Nested(ImagePathFilterSchema(), allow_none=True)
    objective = fields.Nested(ObjectivesSchema(), allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return OpticalPath(**data)
