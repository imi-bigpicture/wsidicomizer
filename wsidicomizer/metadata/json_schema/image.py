#    Copyright 2023 SECTRA AB
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

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
    focus_method = fields.Enum(FocusMethod, by_value=True, allow_none=True)
    extended_depth_of_field = fields.Nested(
        ExtendedDepthOfFieldSchema(), allow_none=True
    )
    image_coordinate_system = fields.Nested(
        ImageCoordinateSystemSchema(), allow_none=True
    )

    @post_load
    def load_to_object(self, data, **kwargs):
        return Image(**data)
