from typing import Any, Dict, Type
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from marshmallow import fields, post_load, pre_dump
from wsidicomizer.metadata.dicom_schema.dicom_fields import BooleanDicomField

from wsidicomizer.metadata.label import Label
from wsidicom.instance import ImageType


class LabelDicomSchema(DicomSchema[Label]):
    """
    type 1
    burned_in_annotation
    specimen_label_in_image

    type 2
    text (if label type)
    barcode (if label type)
    """

    text = fields.String(data_key="LabelText", allow_none=True)
    barcode = fields.String(data_key="BarcodeValue", allow_none=True)
    label_in_volume_image = BooleanDicomField(load_only=True, allow_none=True)
    label_in_overview_image = BooleanDicomField(load_only=True, allow_none=True)
    label_is_phi = BooleanDicomField(load_only=True, allow_none=True)
    burned_in_annotation = BooleanDicomField(data_key="BurnedInAnnotation")
    specimen_label_in_image = BooleanDicomField(data_key="SpecimenLabelInImage")
    image_type = fields.List(fields.String(), load_only=True, data_key="ImageType")

    @property
    def load_type(self) -> Type[Label]:
        return Label

    @pre_dump
    def pre_dump(self, label: Label, **kwargs):
        image_type = self.context.get("image_type", None)
        label_in_image = False
        contains_phi = False
        if (
            (image_type == ImageType.VOLUME and label.label_in_volume_image)
            or (image_type == ImageType.OVERVIEW and label.label_in_overview_image)
            or image_type == ImageType.LABEL
        ):
            label_in_image = "True"
            contains_phi = label.label_is_phi
        attributes = {
            "burned_in_annotation": contains_phi,
            "specimen_label_in_image": label_in_image,
        }
        # Label image type should have text and barcode even if empty
        label_required_fields = {"text": label.text, "barcode": label.barcode}
        for key, value in label_required_fields.items():
            if image_type == ImageType.LABEL or value is not None:
                attributes[key] = value
        return attributes

    @post_load
    def post_load(self, data: Dict[str, Any], **kwargs):
        image_type = ImageType(data.pop("image_type")[2])
        burned_in_annotation = data.pop("burned_in_annotation")
        specimen_label_in_image = data.pop("specimen_label_in_image")
        label_is_phi = False
        label_in_volume_image = False
        label_in_overview_image = False
        if image_type == ImageType.LABEL:
            label_is_phi = burned_in_annotation
        elif image_type == ImageType.VOLUME and specimen_label_in_image:
            label_is_phi = burned_in_annotation
            label_in_volume_image = True
        elif image_type == ImageType.OVERVIEW and specimen_label_in_image:
            label_is_phi = burned_in_annotation
            label_in_overview_image = True
        data["label_is_phi"] = label_is_phi
        data["label_in_volume_image"] = label_in_volume_image
        data["label_in_overview_image"] = label_in_overview_image
        return super().post_load(data, **kwargs)
