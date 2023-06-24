from marshmallow import Schema, fields, post_load

from wsidicomizer.metadata.equipment import Equipment


class EquipmentSchema(Schema):
    manufacturer = fields.String(allow_none=True)
    model_name = fields.String(allow_none=True)
    device_serial_number = fields.String(allow_none=True)
    software_versions = fields.List(fields.String(), allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return Equipment(**data)
