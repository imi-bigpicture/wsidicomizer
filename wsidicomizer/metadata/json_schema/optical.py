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

from wsidicomizer.metadata.json_schema.fields import JsonFieldFactory


class LightPathFilterJsonSchema(Schema):
    filters = fields.List(JsonFieldFactory.concept_code(LightPathFilterCode)())
    nominal = fields.Float(allow_none=True)
    low_pass = fields.Float(allow_none=True)
    high_pass = fields.Float(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return LightPathFilter(**data)


class ImagePathFilterJsonSchema(Schema):
    filters = fields.List(JsonFieldFactory.concept_code(ImagePathFilterCode)())
    nominal = fields.Float(allow_none=True)
    low_pass = fields.Float(allow_none=True)
    high_pass = fields.Float(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return ImagePathFilter(**data)


class ObjectivesJsonSchema(Schema):
    """Set of lens conditions for optical path"""

    lenses = fields.List(JsonFieldFactory.concept_code(LenseCode))
    condenser_power = fields.Float(allow_none=True)
    objective_power = fields.Float(allow_none=True)
    objective_numerical_aperature = fields.Float(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Objectives(**data)


class OpticalPathJsonSchema(Schema):
    identifier = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    illumination_types = fields.List(
        JsonFieldFactory.concept_code(IlluminationCode)(allow_none=True)
    )
    illumination = JsonFieldFactory.float_or_concept_code(IlluminationColorCode)(
        allow_none=True
    )
    # icc_profile: Optional[bytes] = None
    # lut: Optional[Lut] = None
    light_path_filter = fields.Nested(LightPathFilterJsonSchema(), allow_none=True)
    image_path_filter = fields.Nested(ImagePathFilterJsonSchema(), allow_none=True)
    objective = fields.Nested(ObjectivesJsonSchema(), allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return OpticalPath(**data)
