from marshmallow import Schema, fields, post_load

from wsidicomizer.metadata.image import (
    ExtendedDepthOfField,
    FocusMethod,
    Image,
    ImageCoordinateSystem,
)
from wsidicomizer.metadata.schema.fields import PointMmField


class ExtendedDepthOfFieldSchema(Schema):
    number_of_focal_planes = fields.Integer()
    distance_between_focal_planes = fields.Float()

    @post_load
    def load_to_object(self, data, **kwargs):
        return ExtendedDepthOfField(**data)


class ImageCoordinateSystemSchema(Schema):
    origin = PointMmField()
    rotation = fields.Float()

    @post_load
    def load_to_object(self, data, **kwargs):
        return ImageCoordinateSystem(**data)


class ImageSchema(Schema):
    acquisition_datetime = fields.DateTime(allow_none=True)
    focus_method = fields.Enum(FocusMethod, by_value=False, allow_none=True)
    extended_depth_of_field = fields.Nested(
        ExtendedDepthOfFieldSchema(), allow_none=True
    )
    image_coordinate_system = fields.Nested(
        ImageCoordinateSystemSchema(), allow_none=True
    )

    @post_load
    def load_to_object(self, data, **kwargs):
        return Image(**data)
