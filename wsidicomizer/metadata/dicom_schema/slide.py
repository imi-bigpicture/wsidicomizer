from typing import Any, Dict, List, Optional, Type, Union
from highdicom import SpecimenStaining
from marshmallow import pre_dump, post_dump, pre_load, post_load
from pydicom import Dataset
from wsidicomizer.metadata.defaults import Defaults
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from marshmallow import fields
from wsidicom.conceptcode import (
    ContainerComponentTypeCode,
    ContainerTypeCode,
    SpecimenStainsCode,
    ConceptCode,
)
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    CodeDicomField,
    DateTimeDicomField,
    DefaultingDicomField,
    SingleCodeDicomField,
    UidDicomField,
)
from pydicom.sr.coding import Code
from wsidicomizer.metadata.sample import SlideSample, Staining

from wsidicomizer.metadata.slide import Slide


# class StainingDicomSchema(DicomSchema):
#     substances = fields.List
#     date_time = DateTimeDicomField()

#     @pre_load
#     def pre_load(self, dataset: Dataset, **kwargs):
#         assert isinstance(dataset.processing_procedure, SpecimenStaining)
#         substances: List[Union[str, SpecimenStainsCode]] = []
#         for substance in dataset.processing_procedure.substances:
#             if isinstance(substance, CodedConcept):
#                 substances.append(SpecimenStainsCode(substance.meaning))
#             elif isinstance(substance, str):
#                 substances.append(substance)
#             else:
#                 raise TypeError(
#                     f"Unknown type {type(substance)} for substance {substance}."
#                 )
#         return {"substances": substances}

#     @property
#     def load_type(self) -> Type[Staining]:
#         return Staining


# class SampleDicomSchema(DicomSchema):
#     identifier = fields.String()
#     anatomical_sites = fields.List(CodeDicomField(Code))
#     sampled_from = fields.Nested()
#     uid = UidDicomField()
#     position = fields.String()
#     steps = fields.List(fields.Nested())

#     @property
#     def load_type(self) -> Type[SlideSample]:
#         return SlideSample


class SlideDicomSchema(DicomSchema):
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
                slide_sample.to_description(slide.stainings)
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
            samples, stainings = SlideSample.from_dataset(specimen_description_sequence)
            data["SpecimenDescriptionSequence"] = samples
            data["stainings"] = stainings
        else:
            data["SpecimenDescriptionSequence"] = None
            data["stainings"] = None
        return data
