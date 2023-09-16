from marshmallow import Schema, fields, post_load

from wsidicomizer.metadata.json_schema.equipment import EquipmentSchema
from wsidicomizer.metadata.json_schema.fields import UidField
from wsidicomizer.metadata.json_schema.image import ImageSchema
from wsidicomizer.metadata.json_schema.label import LabelSchema
from wsidicomizer.metadata.json_schema.optical import OpticalPathSchema
from wsidicomizer.metadata.json_schema.patient import PatientSchema
from wsidicomizer.metadata.json_schema.series import SeriesSchema
from wsidicomizer.metadata.json_schema.slide import SlideSchema
from wsidicomizer.metadata.json_schema.study import StudySchema
from wsidicomizer.metadata.wsi import WsiMetadata


class WsiMetadataSchema(Schema):
    study = fields.Nested(StudySchema(), allow_none=True)
    series = fields.Nested(SeriesSchema(), allow_none=True)
    patient = fields.Nested(PatientSchema(), allow_none=True)
    equipment = fields.Nested(EquipmentSchema(), allow_none=True)
    optical_paths = fields.List(fields.Nested(OpticalPathSchema()))
    slide = fields.Nested(SlideSchema(), allow_none=True)
    label = fields.Nested(LabelSchema(), allow_none=True)
    image = fields.Nested(ImageSchema(), allow_none=True)
    frame_of_reference_uid = UidField(allow_none=True)
    dimension_organization_uid = UidField(allow_none=True)

    @post_load
    def load_to_object(self, data, **kwargs):
        return WsiMetadata(**data)
