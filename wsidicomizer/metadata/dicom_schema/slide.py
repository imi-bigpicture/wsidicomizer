from typing import Any, Dict, List, Optional, Type, Union

from highdicom import SpecimenStaining
from marshmallow import fields, post_dump, post_load, pre_dump, pre_load
from pydicom import Dataset
from wsidicom.conceptcode import ContainerTypeCode

from wsidicomizer.metadata.defaults import Defaults
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    DefaultingDicomField,
    SingleCodeDicomField,
)
from wsidicomizer.metadata.dicom_schema.sample import SlideSampleDicom
from wsidicomizer.metadata.slide import Slide


class SlideDicomSchema(DicomSchema[Slide]):
    """
    IssuerOfTheContainerIdentifierSequence
    ContainerComponentSequence:
        ContainerComponentTypeCodeSequence
        ContainerComponentMaterial
    """

    identifier = DefaultingDicomField(
        fields.String(), dump_default=Defaults.string, data_key="ContainerIdentifier"
    )
    stainings = fields.List(fields.Field, load_only=True)
    samples = fields.List(fields.Field, data_key="SpecimenDescriptionSequence")
    container_type = SingleCodeDicomField(
        ContainerTypeCode,
        data_key="ContainerTypeCodeSequence",
        dump_only=True,
        dump_default=Defaults.slide_container_type,
    )

    @property
    def load_type(self) -> Type[Slide]:
        return Slide

    @pre_dump
    def pre_dump(self, slide: Slide, **kwargs):
        # move staining to samples so that sample field can serialize both
        if slide.samples is not None:
            samples = [
                SlideSampleDicom.to_dataset(slide_sample, slide.stainings)
                for slide_sample in slide.samples
            ]
        else:
            samples = []
        return {"identifier": slide.identifier, "samples": samples}

    @post_dump
    def post_dump(self, data: Dict[str, Any], **kwargs):
        data["IssuerOfTheContainerIdentifierSequence"] = []
        data["ContainerComponentSequence"] = []
        return super().post_dump(data, **kwargs)

    @pre_load
    def pre_load(self, dataset: Dataset, **kwargs):
        # move staining steps from SpecimenDescriptionSequence to staining
        data = super().pre_load(dataset, **kwargs)
        specimen_description_sequence = data.pop("SpecimenDescriptionSequence", None)
        if specimen_description_sequence is not None:
            samples, stainings = SlideSampleDicom().from_dataset(
                specimen_description_sequence
            )
            data["SpecimenDescriptionSequence"] = samples
            data["stainings"] = stainings
        else:
            data["SpecimenDescriptionSequence"] = None
            data["stainings"] = None
        return data
