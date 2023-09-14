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
import datetime
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    Union,
)

from marshmallow import Schema, fields, post_load, pre_dump
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationStepsCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
)

from wsidicomizer.metadata.sample import (
    Collection,
    Embedding,
    ExtractedSpecimen,
    Fixation,
    PreparationStep,
    Processing,
    Sample,
    SampledSpecimen,
    Sampling,
    SlideSample,
    Specimen,
    SpecimenIdentifier,
    Staining,
)
from wsidicomizer.metadata.schema.fields import (
    CodeField,
    FieldFactory,
    SlideSamplePositionField,
    SpecimenIdentifierField,
    UidField,
)


"""For sampling steps referencing other sampling steps in sampling_chain_constraints we
have a problem on how to serialize/deserialize. Suggest to change this linkage
with the identifier of the sampled specimen and the number of the sampling step. Add
a dataclass like:
class SamplingChaingConstraintSimplified:
    specimen: Union[str, SpecimenIdentifier]
    sampling_step_index: int

When we deserialize a specimens we check if the sampled specimen is already created,
and if not create that one first. The specimen in the sampling chain constraint should thus also
already be created.
"""


@dataclasses.dataclass
class SerializedSamplingChainConstraint:
    """Simplified representation of a sampling chain constraint, replacing the sampling
    with the identifier of the sampled specimen and the index of the sampling step
    within the step sequence of the specimen."""

    identifier: Union[str, SpecimenIdentifier]
    sampling_step_index: int


@dataclasses.dataclass
class SerializedSampling:
    """Simplified representation of a `Sampling`, replacing the sampled specimen with
    the idententifier and sampling constratins with simplified sampling constraints."""

    method: SpecimenSamplingProcedureCode
    sampling_chain_constraints: Optional[
        Sequence[SerializedSamplingChainConstraint]
    ] = None
    date_time: Optional[datetime.datetime] = None
    description: Optional[str] = None


class SamplingConstraintSchema(Schema):
    """Schema for serializing and deserializing a `SerializedSamplingChainConstraint`."""

    identifier = SpecimenIdentifierField()
    sampling_step_index = fields.Integer()

    @pre_dump
    def dump_simple(self, sampling: Sampling, **kwargs):
        return SerializedSamplingChainConstraint(
            sampling.specimen.identifier, sampling.index
        )

    @post_load
    def load_simple(self, data: Dict, **kwargs) -> SerializedSamplingChainConstraint:
        return SerializedSamplingChainConstraint(**data)


class BasePreparationStepSchema(Schema):
    """Base schema for serializing and deserializing a `PreparationStep`."""

    _load_class: Type[
        Union[SerializedSampling, Collection, Processing, Embedding, Fixation, Staining]
    ]

    @post_load
    def post_load(
        self, data: Dict[str, Any], **kwargs
    ) -> Union[PreparationStep, SerializedSampling]:
        """Return a object of given load class using the defined dataclass fields."""
        return self._load_class(
            **{
                field.name: data[field.name]
                for field in dataclasses.fields(self._load_class)
                if field.name in data
            }
        )


class SamplingSchema(BasePreparationStepSchema):
    method = FieldFactory.concept_code(SpecimenSamplingProcedureCode)()
    sampling_chain_constraints = fields.List(
        fields.Nested(SamplingConstraintSchema, allow_none=True), allow_none=True
    )
    date_time = fields.DateTime(allow_none=True)
    description = fields.String(allow_none=True)
    preparation_type = fields.Constant("sampling")
    _load_class = SerializedSampling


class CollectionSchema(BasePreparationStepSchema):
    method = FieldFactory.concept_code(SpecimenCollectionProcedureCode)()
    date_time = fields.DateTime(allow_none=True)
    description = fields.String(allow_none=True)
    preparation_type = fields.Constant("collection")
    _load_class = Collection


class ProcessingSchema(BasePreparationStepSchema):
    method = FieldFactory.concept_code(SpecimenPreparationStepsCode)()
    date_time = fields.DateTime(allow_none=True)
    preparation_type = fields.Constant("processing")
    _load_class = Processing


class EmbeddingSchema(BasePreparationStepSchema):
    medium = FieldFactory.concept_code(SpecimenEmbeddingMediaCode)()
    date_time = fields.DateTime(allow_none=True)
    preparation_type = fields.Constant("embedding")
    _load_class = Embedding


class FixationSchema(BasePreparationStepSchema):
    fixative = FieldFactory.concept_code(SpecimenFixativesCode)()
    date_time = fields.DateTime(allow_none=True)
    preparation_type = fields.Constant("fixation")
    _load_class = Fixation


class StainingSchema(BasePreparationStepSchema):
    substances = fields.List(
        FieldFactory.concept_code(SpecimenStainsCode)(), allow_none=True
    )
    date_time = fields.DateTime(allow_none=True)
    _load_class = Staining


class PreparationStepSchema(Schema):
    """Schema to use to serialize/deserialize preparation steps."""

    """Mapping step type to schema."""
    _type_to_schema_mapping: Dict[Type[PreparationStep], Type[Schema]] = {
        Sampling: SamplingSchema,
        Collection: CollectionSchema,
        Processing: ProcessingSchema,
        Embedding: EmbeddingSchema,
        Fixation: FixationSchema,
    }

    """Mapping string in `preparation_type` of object to schema."""
    _string_to_schema_mapping: Dict[str, Type[Schema]] = {
        "sampling": SamplingSchema,
        "collection": CollectionSchema,
        "processing": ProcessingSchema,
        "embedding": EmbeddingSchema,
        "fixation": FixationSchema,
    }

    def dump(
        self,
        data: Union[PreparationStep, Iterable[PreparationStep]],
        **kwargs,
    ):
        if isinstance(data, PreparationStep):
            return self._subschema_dump(data)
        return [self._subschema_dump(item) for item in data]

    def load(
        self,
        data: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
        **kwargs,
    ):
        if isinstance(data, Mapping):
            return self._subschema_load(data)
        return [self._subschema_load(step) for step in data]

    def _subschema_load(
        self, step: Mapping
    ) -> Union[PreparationStep, SerializedSampling]:
        """Select a schema and load and return step using the schema."""
        preparation_type = step["preparation_type"]
        schema = self._string_to_schema_mapping[preparation_type]
        loaded = schema().load(step, many=False)
        assert isinstance(loaded, (PreparationStep, SerializedSampling))
        return loaded

    def _subschema_dump(self, step: PreparationStep):
        """Select a schema and dump the step using the schema."""
        schema = self._type_to_schema_mapping[type(step)]
        return schema().dump(step, many=False)


class BaseSpecimenSchema(Schema):
    """Base schema for specimen."""

    identifier = SpecimenIdentifierField()
    steps = fields.List(fields.Nested(PreparationStepSchema()))


class ExtractedSpecimenSchema(BaseSpecimenSchema):
    """Schema for extracted specimen that has not been sampled from other specimen."""

    type = FieldFactory.concept_code(AnatomicPathologySpecimenTypesCode)()
    specimen_type = fields.Constant("extracted")


class SampleSchema(BaseSpecimenSchema):
    """Schema for sampled specimen."""

    sampled_from = fields.List(fields.Nested(SamplingConstraintSchema))
    type = FieldFactory.concept_code(AnatomicPathologySpecimenTypesCode)()
    specimen_type = fields.Constant("sample")


class SlideSampleSchema(BaseSpecimenSchema):
    """Schema for sampled specimen on a slide."""

    anatomical_sites = fields.List(CodeField())
    sampled_from = fields.Nested(SamplingConstraintSchema)
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
        **kwargs,
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
        data: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
        **kwargs,
    ) -> List[Specimen]:
        """Load serialized specimen or list of specimen as `Specimen`."""
        if isinstance(data, Mapping):
            loaded = [self._subschema_load(data)]
        else:
            loaded = [self._subschema_load(item) for item in data]
        return self._post_load(loaded)

    def _subschema_load(self, specimen: Mapping) -> Dict[str, Any]:
        """Select a schema and load and return specimen using the schema."""
        specimen_type = specimen["specimen_type"]
        schema = self._string_to_schema_mapping[specimen_type]
        loaded = schema().load(specimen, many=False)
        assert isinstance(loaded, dict)
        return loaded

    def _subschema_dump(self, specimen: Specimen) -> Dict[str, Any]:
        """Select a schema and dump the specimen using the schema."""
        schema = self._type_to_schema_mapping[type(specimen)]
        dumped = schema().dump(specimen)
        assert isinstance(dumped, dict)
        return dumped

    def _post_load(self, data: Iterable[Dict[str, Any]]) -> List[Specimen]:
        """Post-processing of deserialized dictionary data to linked `Specimen` objects."""
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen] = {}
        specimen_data_by_identifier: Dict[
            Union[str, SpecimenIdentifier], Mapping[str, Any]
        ] = {specimen["identifier"]: specimen for specimen in data}
        for specimen_identifier in specimen_data_by_identifier:
            if specimen_identifier in created_specimens:
                continue
            created_specimens[specimen_identifier] = self._make_specimen(
                specimen_identifier, specimen_data_by_identifier, created_specimens
            )

        # Only return non-sampled specimens (sampled specimens are nested)
        sampled_specimens = [
            sampled_from.specimen.identifier
            for specimen in created_specimens.values()
            if isinstance(specimen, SampledSpecimen)
            for sampled_from in specimen._sampled_from
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
    ) -> Specimen:
        """Create specimen by identifier. Create nested specimens that the specimen
        is sampled from if needed."""
        data = specimen_data[identifier]
        specimen_type = data["specimen_type"]
        print("Making specimen", identifier, specimen_type)

        if specimen_type == "extracted":
            specimen = ExtractedSpecimen(
                identifier=identifier,
                type=data["type"],
            )
        elif specimen_type == "sample":
            sampled_from = cls._get_sampled_from(
                identifier, specimen_data, created_specimens
            )
            specimen = Sample(
                identifier=identifier,
                type=data["type"],
                sampled_from=sampled_from,
            )
        elif specimen_type == "slide":
            sampled_from = cls._get_sampled_from(
                identifier, specimen_data, created_specimens
            )
            if len(sampled_from) == 0:
                parent = None
            elif len(sampled_from) == 1:
                parent = sampled_from[0]
            else:
                raise ValueError()

            specimen = SlideSample(
                identifier=identifier,
                sampled_from=parent,
                anatomical_sites=data["anatomical_sites"],
                uid=data.get("uid"),
                position=data.get("position"),
            )
        else:
            raise TypeError(f"Could not make specimen for unknown type {specimen_type}")

        # Add the steps to the created specimen
        for index, step in enumerate(data.get("steps", [])):
            if isinstance(step, SerializedSampling):
                # Create Sampling step from SerializedSampling step
                constraints = cls._get_sampling_constraints(
                    step, specimen_data, created_specimens
                )
                step = Sampling(
                    specimen, step.method, constraints, step.date_time, step.description
                )
            elif isinstance(step, Collection):
                # Special handling of collection step
                if not isinstance(specimen, ExtractedSpecimen) or index != 0:
                    raise ValueError(
                        (
                            "Collection step can only be added as first step to "
                            " an ExtractedSpecimen"
                        )
                    )
                specimen.extraction_step = step
            assert isinstance(step, PreparationStep)
            specimen.add(step)
        return specimen

    @classmethod
    def _get_sampled_from(
        cls,
        identifier: Union[str, SpecimenIdentifier],
        specimen_data: Dict[Union[str, SpecimenIdentifier], Mapping[str, Any]],
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen],
    ) -> List[Sampling]:
        """
        Get list of `Sampling` used for creating the given specimen.

        Creates sampled specimens if needed.
        """
        data = specimen_data[identifier]
        sampled_from: Optional[
            Union[
                SerializedSamplingChainConstraint,
                Iterable[SerializedSamplingChainConstraint],
            ]
        ] = data.get("sampled_from")
        if sampled_from is None:
            return []
        elif isinstance(sampled_from, SerializedSamplingChainConstraint):
            sampled_from = [sampled_from]
        for sample in sampled_from:
            assert isinstance(sample, SerializedSamplingChainConstraint)
        return [
            cls._get_sampling(sample, specimen_data, created_specimens)
            for sample in sampled_from
        ]

    @classmethod
    def _get_sampling(
        cls,
        sampled_from: SerializedSamplingChainConstraint,
        specimen_data: Dict[Union[str, SpecimenIdentifier], Mapping[str, Any]],
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen],
    ) -> Sampling:
        """
        Get the `Sampling` for a `SerializedSamplingChainConstraint`

        Creates sampled specimens if needed.
        """
        specimen = cls._get_or_create_specimen(
            sampled_from.identifier, specimen_data, created_specimens
        )
        return specimen.samplings[sampled_from.sampling_step_index]

    @classmethod
    def _get_sampling_constraints(
        cls,
        sampling: SerializedSampling,
        specimen_data: Dict[Union[str, SpecimenIdentifier], Mapping[str, Any]],
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen],
    ) -> Optional[List[Sampling]]:
        """
        Get list of constraint `Sampling` for a sampling.
        """
        if sampling.sampling_chain_constraints is None:
            return None
        return [
            cls._get_sampling(constraint, specimen_data, created_specimens)
            for constraint in sampling.sampling_chain_constraints
        ]

    @classmethod
    def _get_or_create_specimen(
        cls,
        identifier: Union[str, SpecimenIdentifier],
        specimen_data: Dict[Union[str, SpecimenIdentifier], Mapping[str, Any]],
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen],
    ) -> Specimen:
        """
        Return `Specimen` by identifier.

        The specimen is either from already created specimens or created.
        """
        if identifier not in created_specimens:
            created_specimens[identifier] = cls._make_specimen(
                identifier,
                specimen_data,
                created_specimens,
            )
        return created_specimens[identifier]
