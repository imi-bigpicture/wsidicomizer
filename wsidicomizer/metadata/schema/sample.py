"""
Schemata for serializing/deserializing Specimen.

To avoid duplication in the nested `sampled_from` attribute, the `SampledFrom` object
is serialized to a `SampledFromSimplified` replacing the linked specimen with the
identifier of the specimen.

The collection of specimens in a sampling hierarchy can be serialized/deserialized using
the `SpecimenSchema`, which serializes all the contained specimens individually and, on
deserialization, recreates the specimen object linkage in the `sampled_from` attribute.
"""
import dataclasses
from typing import Any, Dict, Iterable, Mapping, Optional, Type, Union

from marshmallow import Schema, fields, post_load, pre_dump, types
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationStepsCode,
    SpecimenSamplingProcedureCode,
)

from wsidicomizer.metadata.sample import (
    Collection,
    Embedding,
    ExtractedSpecimen,
    Fixation,
    PreparationStep,
    Processing,
    Sample,
    SampledFrom,
    SampledSpecimen,
    Sampling,
    SlideSample,
    Specimen,
    SpecimenIdentifier,
)
from wsidicomizer.metadata.schema.fields import (
    CodeField,
    FieldFactory,
    SlideSamplePositionField,
    SpecimenIdentifierField,
    UidField,
)


@dataclasses.dataclass
class SampledFromSimplified:
    specimen: Union[str, SpecimenIdentifier]
    sub_samplings: Optional[Iterable[Union[str, SpecimenIdentifier]]] = None


class SamplingSchema(Schema):
    sample_identifier = SpecimenIdentifierField()
    method = FieldFactory.concept_code(SpecimenSamplingProcedureCode)()
    subspecimens = fields.List(SpecimenIdentifierField(), allow_none=True)
    date_time = fields.DateTime(allow_none=True)
    description = fields.String(allow_none=True)
    preparation_type = fields.Constant("sampling")


class CollectionSchema(Schema):
    method = FieldFactory.concept_code(SpecimenCollectionProcedureCode)()
    date_time = fields.DateTime(allow_none=True)
    description = fields.String(allow_none=True)
    preparation_type = fields.Constant("collection")


class ProcessingSchema(Schema):
    method = FieldFactory.concept_code(SpecimenPreparationStepsCode)()
    date_time = fields.DateTime(allow_none=True)
    preparation_type = fields.Constant("processing")


class EmbeddingSchema(Schema):
    medium = FieldFactory.concept_code(SpecimenEmbeddingMediaCode)()
    date_time = fields.DateTime(allow_none=True)
    preparation_type = fields.Constant("embedding")


class FixationSchema(Schema):
    fixative = FieldFactory.concept_code(SpecimenFixativesCode)()
    date_time = fields.DateTime(allow_none=True)
    preparation_type = fields.Constant("fixation")


class PreparationStepSchema(Schema):
    _type_to_schema_mapping: Dict[Type[PreparationStep], Type[Schema]] = {
        Sampling: SamplingSchema,
        Collection: CollectionSchema,
        Processing: ProcessingSchema,
        Embedding: EmbeddingSchema,
        Fixation: FixationSchema,
    }

    _string_to_type_mapping: Dict[
        str, Type[Union[Sampling, Collection, Processing, Embedding, Fixation]]
    ] = {
        "sampling": Sampling,
        "collection": Collection,
        "processing": Processing,
        "embedding": Embedding,
        "fixation": Fixation,
    }

    def dump(
        self,
        data: Union[PreparationStep, Iterable[PreparationStep]],
        *,
        many: bool | None = None,
    ):
        if isinstance(data, PreparationStep):
            return self._subschema_dump(data)
        return [self._subschema_dump(item) for item in data]

    def load(
        self,
        data: Mapping[str, Any] | Iterable[Mapping[str, Any]],
        *,
        many: bool | None = None,
        partial: types.StrSequenceOrSet | bool | None = None,
        unknown: str | None = None,
        **kwargs,
    ):
        if isinstance(data, Mapping):
            return self._subschema_load(data)
        return [self._subschema_load(step) for step in data]

    def _subschema_load(self, step: Mapping) -> PreparationStep:
        preparation_type = step["preparation_type"]
        load_class = self._string_to_type_mapping[preparation_type]
        schema = self._type_to_schema_mapping[load_class]
        loaded = schema().load(step, many=False)
        assert isinstance(loaded, Mapping)
        return load_class(
            **{
                field.name: loaded[field.name]
                for field in dataclasses.fields(load_class)
                if field.name in loaded
            }
        )

    def _subschema_dump(self, step: PreparationStep):
        schema = self._type_to_schema_mapping[type(step)]
        return schema().dump(step, many=False)


class SampledFromSchema(Schema):
    identifier = SpecimenIdentifierField()
    sub_samplings = fields.List(SpecimenIdentifierField(), allow_none=True)

    @pre_dump
    def dump_simple(self, sampled_from: SampledFrom, **kwargs) -> SampledFromSimplified:
        """Convert to a simplified object replacing the specimen object with its identifier."""
        return SampledFromSimplified(
            specimen=sampled_from.specimen.identifier,
            sub_samplings=sampled_from.sub_sampling,
        )

    @post_load
    def load_simple(self, data: Dict, **kwargs) -> SampledFromSimplified:
        """Load back the simplified object."""
        return SampledFromSimplified(data["specimen"], data.get("sub_samplings", None))


class BaseSpecimenSchema(Schema):
    """Base schema for specimen."""

    identifier = SpecimenIdentifierField()
    steps = fields.List(fields.Nested(PreparationStepSchema()))


class BaseSampledSpecimenSchema(BaseSpecimenSchema):
    """Base schema for sampled specimen."""

    sampling_method = FieldFactory.concept_code(SpecimenSamplingProcedureCode)()
    sampled_from = fields.List(fields.Nested(SampledFromSchema()))

    sampling_datetime = fields.DateTime(allow_none=True)
    sampling_description = fields.String(allow_none=True)


class ExtractedSpecimenSchema(BaseSpecimenSchema):
    """Schema for extracted specimen that has not been sampled from other specimen."""

    type = FieldFactory.concept_code(AnatomicPathologySpecimenTypesCode)()
    extraction_method = FieldFactory.concept_code(SpecimenCollectionProcedureCode)(
        allow_none=True
    )
    extraction_datetime = fields.DateTime(allow_none=True)
    extraction_description = fields.String(allow_none=True)
    specimen_type = fields.Constant("extracted")


class SampleSchema(BaseSampledSpecimenSchema):
    """Schema for sampled specimen."""

    type = FieldFactory.concept_code(AnatomicPathologySpecimenTypesCode)()
    specimen_type = fields.Constant("sample")


class SlideSampleSchema(BaseSampledSpecimenSchema):
    """Schema for sampled specimen on a slide."""

    anatomical_sites = fields.List(CodeField())
    uid = UidField(allow_none=True)
    position = SlideSamplePositionField(allow_none=True)
    specimen_type = fields.Constant("slide")


class SpecimenSchema(Schema):
    """Schema to use to serialize/deserialize specimens."""

    """Mapping specimen type to schema."""
    _type_to_schema_mapping: Dict[Type[Specimen], Type[Schema]] = {
        ExtractedSpecimen: ExtractedSpecimenSchema,
        Sample: SampleSchema,
        SlideSample: SlideSampleSchema,
    }

    """Mapping string in `specimen_type` of object to schema."""
    _string_to_schema_mapping: Dict[str, Type[Schema]] = {
        "extracted": ExtractedSpecimenSchema,
        "sample": SampleSchema,
        "slide": SlideSampleSchema,
    }

    def dump(
        self,
        specimens: Union[Specimen, Iterable[Specimen]],
        *,
        many: bool | None = None,
    ):
        if isinstance(specimens, Specimen):
            specimens = [specimens]
        all_specimens: Dict[Union[str, SpecimenIdentifier], Specimen] = {}

        for specimen in specimens:
            if isinstance(specimen, SampledSpecimen):
                all_specimens.update(specimen.get_samplings())
        return [self._subschema_dump(specimen) for specimen in all_specimens.values()]

    def load(
        self,
        data: Mapping[str, Any] | Iterable[Mapping[str, Any]],
        *,
        many: bool | None = None,
        partial: types.StrSequenceOrSet | bool | None = None,
        unknown: str | None = None,
        **kwargs,
    ):
        if isinstance(data, Mapping):
            loaded = [self._subschema_load(data)]
        else:
            loaded = [self._subschema_load(item) for item in data]
        return self._post_load(loaded)

    def _subschema_load(self, specimen: Mapping) -> Any:
        specimen_type = specimen["specimen_type"]
        schema = self._string_to_schema_mapping[specimen_type]
        return schema().load(specimen, many=False)

    def _subschema_dump(self, specimen: Specimen):
        schema = self._type_to_schema_mapping[type(specimen)]
        return schema().dump(specimen)

    def _post_load(self, data: Iterable[Mapping[str, Any]]):
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen] = {}
        specimen_data_by_identifier: Dict[
            Union[str, SpecimenIdentifier], Mapping[str, Any]
        ] = {specimen["identifier"]: specimen for specimen in data}
        for specimen in data:
            specimen_identifier = specimen["identifier"]
            if specimen_identifier in created_specimens:
                continue
            created_specimens[specimen_identifier] = self._make_specimen(
                specimen_identifier, specimen_data_by_identifier, created_specimens
            )
        sampled_specimens = [
            sampled_from.specimen.identifier
            for specimen in created_specimens.values()
            if isinstance(specimen, SampledSpecimen)
            for sampled_from in specimen.sampled_from
        ]
        return [
            specimen
            for specimen in created_specimens.values()
            if specimen.identifier not in sampled_specimens
        ]

    @classmethod
    def _make_specimen(
        cls,
        identifier: Union[str, SpecimenIdentifier],
        specimen_data: Dict[Union[str, SpecimenIdentifier], Mapping[str, Any]],
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen],
    ):
        data = specimen_data[identifier]
        specimen_type = data["specimen_type"]
        if specimen_type == "extracted":
            return ExtractedSpecimen(
                identifier=identifier,
                type=data["type"],
                extraction_method=data["extraction_method"],
                extraction_datetime=data["extraction_datetime"],
                extraction_description=data["extraction_description"],
                steps=data["steps"],
            )
        sampled_from: Iterable[SampledFromSimplified] = data["sampled_from"]
        if sampled_from is not None:
            for sampling in sampled_from:
                if sampling.specimen not in created_specimens:
                    created_specimens[sampling.specimen] = cls._make_specimen(
                        sampling.specimen,
                        specimen_data,
                        created_specimens,
                    )

            parents = [
                SampledFrom(
                    created_specimens[parent_sample.specimen],
                    parent_sample.sub_samplings,
                )
                for parent_sample in sampled_from
            ]
        else:
            parents = []
        if specimen_type == "sample":
            return Sample(
                identifier=identifier,
                type=data["type"],
                sampling_method=data["sampling_method"],
                sampling_datetime=data["sampling_datetime"],
                sampling_description=data["sampling_description"],
                steps=data["steps"],
                sampled_from=parents,
            )
        if specimen_type == "slide":
            return SlideSample(
                identifier=identifier,
                sampling_method=data["sampling_method"],
                sampling_datetime=data["sampling_datetime"],
                sampling_description=data["sampling_description"],
                sampled_from=parents,
                anatomical_sites=data["anatomical_sites"],
                uid=data["uid"],
                position=data["position"],
            )
        raise TypeError(f"Could not make specimen for unknown type {specimen_type}")
