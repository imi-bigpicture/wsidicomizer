from marshmallow import Schema, fields, post_load

from wsidicomizer.metadata.schema.equipment import EquipmentSchema
from wsidicomizer.metadata.schema.fields import UidField
from wsidicomizer.metadata.schema.image import ImageSchema
from wsidicomizer.metadata.schema.label import LabelSchema
from wsidicomizer.metadata.schema.optical import OpticalPathSchema
from wsidicomizer.metadata.schema.patient import PatientSchema
from wsidicomizer.metadata.schema.series import SeriesSchema
from wsidicomizer.metadata.schema.slide import SlideSchema
from wsidicomizer.metadata.schema.study import StudySchema
from wsidicomizer.metadata.wsi import WsiMetadata


class WsiSchema(Schema):
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
