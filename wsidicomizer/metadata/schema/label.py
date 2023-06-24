from marshmallow import Schema, fields, post_load

from wsidicomizer.metadata.label import Label


class LabelSchema(Schema):
    label_text = fields.String(allow_none=True)
    barcode_value = fields.String(allow_none=True)
    label_in_volume_image = fields.Boolean(load_default=False, allow_none=True)
    label_in_overview_image = fields.Boolean(load_default=False, allow_none=True)
    label_is_phi = fields.Boolean(load_default=True, allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Label(**data)
