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
