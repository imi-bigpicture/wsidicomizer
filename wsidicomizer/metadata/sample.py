import datetime
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from highdicom import (
    IssuerOfIdentifier,
    SpecimenCollection,
    SpecimenDescription,
    SpecimenPreparationStep,
    SpecimenProcessing,
    SpecimenSampling,
    SpecimenStaining,
    UniversalEntityIDTypeValues,
)
from pydicom import Dataset
from pydicom.sr.coding import Code
from pydicom.uid import UID, generate_uid
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationStepsCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
)


"""
A root specimen is created by giving it an identifier, a type, and optionally the
extraction method used.

To any specimen steps can be added. These are added to a list of steps, representing the
order that the specimen was processed.

A sampled specimen is created by one or more parent specimens, a sampling method, a type,
and an identifier.
The sampling can optionally be specific the to one or more specimens in the parent specimen.
A sampled specimen keeps track of the specimens it was sampled from. A sampling step is added to the parent
specimen representing the sampling (defining the sampling method, the sub-specimen
sampled (if not whole specimen), and the identifier of the new sample.)

Finally a slide sample will be made (using a create_slide_sample()-method?). The slide
sample has added position.

When DICOMizing the chain of samples, we start at the slide sample. For each specimen, we
process the steps in reverse order and convert the steps into SpecimenPreparationSteps.
For a Sample-specimen We then go to the linked sampled_from specimens and find the step
corresponding to the sampling, and parse all the steps prior to that step (again in reverse
order). Finally we end up at the TakenSpecimen which does not have a parent specimen.

When we parse the parent specimen steps for a sample, we only consider steps (processing
and sampling) the for sub-specimens in the parent the sample was sampled from, if specified.
E.g. there might be steps specific to one of the parent specimens samples, that is or is not
included. We only follow the sampled_from linkage of the given specimen.

Highdicom does not support the Specimen Receiving and Specimen Storage steps, so skip those.
Highdicom does not support Specimen Container and Specimen Type in the SpecimenPreparationStep,
consider making a PR.
"""


@dataclass(unsafe_hash=True)
class SpecimenIdentifier:
    """A specimen identifier including an optional issuer."""

    value: str
    issuer: Optional[str] = None
    issuer_type: Optional[Union[str, UniversalEntityIDTypeValues]] = None

    def __eq__(self, other: Any):
        if isinstance(other, str):
            return self.value == other and self.issuer is None
        if isinstance(other, SpecimenIdentifier):
            return self.value == other.value and self.issuer == other.issuer
        return False

    def to_identifier_and_issuer(self) -> Tuple[str, Optional[IssuerOfIdentifier]]:
        if self.issuer is None:
            return self.value, None
        return self.value, IssuerOfIdentifier(self.issuer, self.issuer_type)

    @classmethod
    def get_identifier_and_issuer(
        cls, identifier: Union[str, "SpecimenIdentifier"]
    ) -> Tuple[str, Optional[IssuerOfIdentifier]]:
        """Return string identifier and optional issuer of identifier object."""
        if isinstance(identifier, str):
            return identifier, None
        return identifier.to_identifier_and_issuer()


class PreparationStep(metaclass=ABCMeta):
    """A generic preparation step that represents a preparation action that was performed
    on a specimen."""

    @abstractmethod
    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        """Return a formatted `SpecimenPreparationStep` for the step."""
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "PreparationStep":
        """Create a step from parsing of a `SpecimenPreparationStep`."""
        raise NotImplementedError()

    @staticmethod
    def _get_identifier(
        dataset: SpecimenPreparationStep,
    ) -> Union[str, SpecimenIdentifier]:
        """Return identifier for step."""
        if dataset.issuer_of_specimen_id is not None:
            return SpecimenIdentifier(
                dataset.specimen_id, dataset.issuer_of_specimen_id
            )
        return dataset.specimen_id


@dataclass
class Sampling(PreparationStep):
    """The sampling of a specimen into a new (sample) specimen."""

    specimen: "Specimen"
    method: SpecimenSamplingProcedureCode
    sampling_chain_constraints: Optional[Sequence["Sampling"]] = None
    date_time: Optional[datetime.datetime] = None
    description: Optional[str] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        parent_identifier, parent_issuer = SpecimenIdentifier.get_identifier_and_issuer(
            self.specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenSampling(
                method=self.method.code,
                parent_specimen_id=parent_identifier,
                parent_specimen_type=specimen.type.code,
                issuer_of_parent_specimen_id=parent_issuer,
            ),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
            processing_description=self.description,
        )

    def to_preparation_steps(
        self, specimen: "Specimen"
    ) -> List[SpecimenPreparationStep]:
        steps = []
        steps.extend(self.specimen.to_preparation_steps_for_sampling(self))
        steps.append(self.to_preparation_step(specimen))
        return steps

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "Sampling":
        assert isinstance(dataset.processing_procedure, SpecimenSampling)
        identifier = cls._get_identifier(dataset)
        # TODO how to figure out sub-sampling?
        raise NotImplementedError()
        # return Sampling(
        #     sample_identifier=identifier,
        #     method=SpecimenSamplingProcedureCode(
        #         dataset.processing_procedure.method.meaning
        #     ),
        #     date_time=dataset.processing_datetime,
        # )


@dataclass
class Collection(PreparationStep):
    """The collection of a specimen."""

    method: SpecimenCollectionProcedureCode
    date_time: Optional[datetime.datetime] = None
    description: Optional[str] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenCollection(procedure=self.method.code),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
            processing_description=self.description,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "Collection":
        assert isinstance(dataset.processing_procedure, SpecimenCollection)
        return Collection(
            SpecimenCollectionProcedureCode(
                dataset.processing_procedure.procedure.meaning
            ),
            date_time=dataset.processing_datetime,
        )


@dataclass
class Processing(PreparationStep):
    """Other processing steps made on a specimen."""

    method: SpecimenPreparationStepsCode
    date_time: Optional[datetime.datetime] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenProcessing(description=self.method.code),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "Processing":
        assert isinstance(dataset.processing_procedure, SpecimenProcessing)
        return Processing(
            SpecimenPreparationStepsCode(
                dataset.processing_procedure.description.meaning
            ),
            date_time=dataset.processing_datetime,
        )


@dataclass
class Embedding(PreparationStep):
    """Embedding of a specimen."""

    medium: SpecimenEmbeddingMediaCode
    date_time: Optional[datetime.datetime] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenProcessing(description="Embedding"),
            embedding_medium=self.medium.code,
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "Embedding":
        assert dataset.embedding_medium is not None
        return Embedding(
            SpecimenEmbeddingMediaCode(dataset.embedding_medium.meaning),
            date_time=dataset.processing_datetime,
        )


@dataclass
class Fixation(PreparationStep):
    """Fixation of a specimen."""

    fixative: SpecimenFixativesCode
    date_time: Optional[datetime.datetime] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenProcessing(description="Fixation"),
            embedding_medium=self.fixative.code,
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "Fixation":
        assert dataset.fixative is not None
        return Fixation(
            SpecimenFixativesCode(dataset.fixative.meaning),
            date_time=dataset.processing_datetime,
        )


class Specimen(metaclass=ABCMeta):
    """A generic specimen."""

    def __init__(
        self,
        identifier: Union[str, SpecimenIdentifier],
        type: AnatomicPathologySpecimenTypesCode,
        steps: Sequence[PreparationStep],
    ):
        self.identifier = identifier
        self.type = type
        self.steps = list(steps)

    @property
    def samplings(self) -> List[Sampling]:
        """Return list of samplings done on the specimen."""
        return [step for step in self.steps if isinstance(step, Sampling)]

    @abstractmethod
    def add(self, step: PreparationStep) -> None:
        """Add a preparation step to the sequence of steps for the specimen."""
        raise NotImplementedError()

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        """Return complete list of formatted steps for this specimen. If specimen
        is sampled include steps for the sampled specimen."""
        steps: List[SpecimenPreparationStep] = []
        if isinstance(self, SampledSpecimen):
            steps.extend(self._get_steps_for_sampling())
        steps.extend(step.to_preparation_step(self) for step in self.steps)
        return steps

    def to_preparation_steps_for_sampling(
        self, sampling: Sampling
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps in this specimen used for the given sampling."""
        steps: List[SpecimenPreparationStep] = []
        if isinstance(self, SampledSpecimen):
            steps.extend(self._get_steps_for_sampling())
        steps.extend(
            step.to_preparation_step(self)
            for step in self._get_steps_before_sampling(sampling)
        )
        return steps

    def _get_steps_before_sampling(
        self, sampling: Sampling
    ) -> Iterator[PreparationStep]:
        """Return the steps in this specimen that occurred before the given sampling."""
        for step in self.steps:
            if isinstance(step, Sampling):
                # Break if sampling step for this sample, otherwise skip
                if step == sampling:
                    break
                continue
            yield step


class SampledSpecimen(Specimen):
    """A specimen thas has been sampled one or more other specimens."""

    def __init__(
        self,
        identifier: Union[str, SpecimenIdentifier],
        type: AnatomicPathologySpecimenTypesCode,
        sampled_from: Sequence[Sampling],
        steps: Sequence[PreparationStep],
    ):
        super().__init__(identifier, type, steps)
        self.sampled_from = sampled_from
        # for sampling in self.sampled_from:
        #     if sampling.sub_sampling is not None:
        #         if not isinstance(sampling.sampled_specimen, SampledSpecimen):
        #             raise ValueError(
        #                 "Can only define sub-sampling for sampled specimens"
        #             )
        #         missing_sub_sampling = sampling.sampled_specimen.get_missing_sub_sampling(
        #             sampling.sub_sampling
        #         )
        #         if missing_sub_sampling is not None:
        #             raise ValueError(
        #                 f"Specimen {sampling.sampled_specimen.identifier} was not sampled from "
        #                 f"given sub-sampling {missing_sub_sampling}"
        #             )

    def add(self, step: PreparationStep) -> None:
        if isinstance(step, Collection):
            raise ValueError(
                "A collection step can only be added to specimens of type `ExtractedSpecimen`"
            )
        self.steps.append(step)

    def _get_steps_for_sampling(self) -> List[SpecimenPreparationStep]:
        """Return formatted steps for the specimen the sample was sampled from."""
        return [
            step
            for sampling in self.sampled_from
            for step in sampling.to_preparation_steps(self)
        ]

    def get_samplings(self) -> Dict[Union[str, SpecimenIdentifier], Specimen]:
        """Return a dictionary containing this specimen and all recursive sampled specimens."""
        samplings: Dict[Union[str, SpecimenIdentifier], Specimen] = {
            self.identifier: self
        }
        for sampling in self.sampled_from:
            if not isinstance(sampling.specimen, SampledSpecimen):
                samplings.update({sampling.specimen.identifier: sampling.specimen})
            else:
                samplings.update(sampling.specimen.get_samplings())
        return samplings

    def sample(
        self,
        method: SpecimenSamplingProcedureCode,
        date_time: Optional[datetime.datetime] = None,
        description: Optional[str] = None,
        sampling_chain_constraints: Optional[Sequence[Sampling]] = None,
    ) -> Sampling:
        """Create a sampling from the specimen that can be used to create a new sample."""
        # TODO?
        # missing_sub_sampling = self.get_missing_sub_sampling(sub_samplings)
        # if missing_sub_sampling is not None:
        #     raise ValueError(
        #         "Could not create sampling as specimen was not sampled "
        #         f"from {missing_sub_sampling}"
        #     )
        if sampling_chain_constraints is not None:
            for sampling_chain_constraint in sampling_chain_constraints:
                assert isinstance(sampling_chain_constraint, Sampling)
        sampling = Sampling(
            specimen=self,
            method=method,
            sampling_chain_constraints=sampling_chain_constraints,
            date_time=date_time,
            description=description,
        )
        self.add(sampling)
        return sampling

    # def get_missing_sub_sampling(
    #     self, sub_samplings: Optional[Iterable[Union[str, SpecimenIdentifier]]]
    # ) -> Optional[Union[str, SpecimenIdentifier]]:
    #     if sub_samplings is None:
    #         return None
    #     sub_sampling_identifiers = [
    #         sample.specimen.identifier for sample in self.sampled_from
    #     ]

    #     def recursive_search(
    #         sub_sampling: Union[str, SpecimenIdentifier], specimen: Specimen
    #     ) -> bool:
    #         if sub_sampling == specimen.identifier:
    #             return True
    #         if isinstance(specimen, SampledSpecimen):
    #             return any(
    #                 recursive_search(sub_sampling, sampling.specimen)
    #                 for sampling in specimen.sampled_from
    #             )
    #         return False

    #     for sub_sampling in sub_samplings:
    #         if not recursive_search(sub_sampling, self):
    #             return sub_sampling
    #     return None

    def sampling_chain_is_ambiguous(
        self, sampling_chain_constraints: Optional[Sequence[Sampling]] = None
    ) -> bool:
        """
        Return true if there is multiple sampling chains possible for this specimen.

        A sampling chain is the series of samplings connecting the sample to an
        extracted specimen. As a sample can be composed from multiple samplings, the
        chain can branch. The sampling chain is ambiguous if it is not possible to
        determine a single chain to an extracted specimen.

        Optionally the sampling chain can be constrained by specifying sampling steps
        that should be in the chain.

        A chain is ambiguous if:
        - It has more than one sampling and sampling_chain_constraints is None
        - Any samplings that are not in the sampling chain constratin is ambiguous.
        """
        if sampling_chain_constraints is not None:
            matching_constraints = [
                sampling
                for sampling in self.sampled_from
                if sampling in sampling_chain_constraints
            ]
            if len(matching_constraints) > 1:
                # Constraining to two branches not possible.
                raise ValueError("Multiple constraints matching on the same sample.")
            if len(matching_constraints) == 1:
                # Constrain to one of the sampling branches.
                constrained_chain = matching_constraints[0]
                sampling_chain_constraints = [
                    sampling_chain_constraint
                    for sampling_chain_constraint in sampling_chain_constraints
                    if sampling_chain_constraint != constrained_chain
                ]
                if not isinstance(constrained_chain.specimen, SampledSpecimen):
                    # Reached the end of the sampling chain.
                    if len(sampling_chain_constraints) != 0:
                        print("end chain with constraints left, True")
                        return True
                    print("end chain with no constraints left, False")
                    return False
                return constrained_chain.specimen.sampling_chain_is_ambiguous(
                    sampling_chain_constraints
                )
            else:
                # No constrains matches
                return any(
                    sampling.specimen.sampling_chain_is_ambiguous(
                        sampling_chain_constraints
                    )
                    for sampling in self.sampled_from
                    if isinstance(sampling.specimen, SampledSpecimen)
                )
        samplings = list(self.sampled_from)
        if len(samplings) > 1:
            print("No constraints and more than one sample, True")
            return True
        if not isinstance(samplings[0].specimen, SampledSpecimen):
            print("No constraints and only one non-sampled sample, False")
            return False
        result = samplings[0].specimen.sampling_chain_is_ambiguous()
        print("Non constraints and only one sampled sample,", result)
        return result


@dataclass
class ExtractedSpecimen(Specimen):
    """A specimen that has been extracted/taken from a patient in some way. Does not
    need to represent the actual first specimen in the collection chain, but should
    represent the first known (i.e. that we have metadata for) specimen in the collection
    chain."""

    identifier: Union[str, SpecimenIdentifier]
    type: AnatomicPathologySpecimenTypesCode
    extraction_step: Optional[Collection] = None
    steps: List[PreparationStep] = field(default_factory=list)

    def __post_init__(self):
        if self.extraction_step is not None:
            self.steps.insert(
                0,
                self.extraction_step,
            )
        else:
            collection_step = next(
                (step for step in self.steps if isinstance(step, Collection)), None
            )
            if collection_step is not None:
                self.extraction_step = collection_step
        super().__init__(identifier=self.identifier, type=self.type, steps=self.steps)

    def add(self, step: PreparationStep) -> None:
        if isinstance(step, Collection) and len(self.steps) != 0:
            raise ValueError("A Collection-step must be the first step.")
        self.steps.append(step)

    def sample(
        self,
        method: SpecimenSamplingProcedureCode,
        date_time: Optional[datetime.datetime] = None,
        description: Optional[str] = None,
    ) -> Sampling:
        """Create a sampling from the specimen that can be used to create a new sample."""
        sampling = Sampling(
            specimen=self,
            method=method,
            sampling_chain_constraints=None,
            date_time=date_time,
            description=description,
        )
        self.add(sampling)
        return sampling


@dataclass
class Sample(SampledSpecimen):
    """A specimen that has been sampled from one or more other specimens."""

    identifier: Union[str, SpecimenIdentifier]
    type: AnatomicPathologySpecimenTypesCode
    sampled_from: Sequence[Sampling]
    steps: Sequence[PreparationStep] = field(default_factory=list)

    def __post_init__(self):
        super().__init__(
            identifier=self.identifier,
            type=self.type,
            sampled_from=self.sampled_from,
            steps=self.steps,
        )


@dataclass
class SlideSamplePosition:
    """The position of a sample on a slide. `x` and `y` in mm and `z` in um."""

    x: float
    y: float
    z: float

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class SlideSample(SampledSpecimen):
    """A sample that has been placed on a slide."""

    identifier: Union[str, SpecimenIdentifier]
    anatomical_sites: Sequence[Code]
    sampled_from: Optional[Sampling] = None
    uid: Optional[UID] = None
    position: Optional[Union[str, SlideSamplePosition]] = None
    steps: List[PreparationStep] = field(init=False, default_factory=list)

    def __post_init__(self):
        # TODO
        if self.sampled_from is None:
            sampled_from = []
        else:
            sampled_from = [self.sampled_from]
        super().__init__(
            identifier=self.identifier,
            type=AnatomicPathologySpecimenTypesCode("Slide"),
            sampled_from=sampled_from,
            steps=self.steps,
        )

    def to_description(
        self,
        stains: Optional[Sequence[SpecimenStainsCode]] = None,
    ) -> SpecimenDescription:
        """Create a formatted specimen description for the specimen."""
        sample_uid = generate_uid() if self.uid is None else self.uid
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        sample_preparation_steps.extend(self.to_preparation_steps())
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            self.identifier
        )
        if stains is not None:
            slide_staining_step = SpecimenPreparationStep(
                identifier,
                processing_procedure=SpecimenStaining([stain.code for stain in stains]),
                issuer_of_specimen_id=issuer,
            )
            sample_preparation_steps.append(slide_staining_step)
        position = None
        if isinstance(self.position, str):
            position = self.position
        elif isinstance(self.position, SlideSamplePosition):
            position = self.position.to_tuple()
        else:
            position = None
        return SpecimenDescription(
            specimen_id=identifier,
            specimen_uid=sample_uid,
            specimen_preparation_steps=sample_preparation_steps,
            specimen_location=position,
            primary_anatomic_structures=[
                anatomical_site for anatomical_site in self.anatomical_sites
            ],
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(
        cls, dataset: Dataset
    ) -> Tuple[List["SlideSample"], List[SpecimenStainsCode]]:
        specimen_descriptions = [
            SpecimenDescription.from_dataset(specimen_description_dataset)
            for specimen_description_dataset in dataset.SpecimenDescriptionSequence
        ]
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen] = {}

        for specimen_description in specimen_descriptions:
            steps: Dict[
                Union[str, SpecimenIdentifier], List[PreparationStep]
            ] = defaultdict(list)
            stains: Dict[
                Union[str, SpecimenIdentifier], List[SpecimenStainsCode]
            ] = defaultdict(list)
            for step in specimen_description.specimen_preparation_steps:
                parsed_steps, parsed_stains = cls._parse_step(step)
                if step.issuer_of_specimen_id is not None:
                    identifier = SpecimenIdentifier(
                        step.specimen_id, step.issuer_of_specimen_id
                    )
                else:
                    identifier = step.specimen_id
                steps[identifier].extend(parsed_steps)
                stains[identifier].extend(parsed_stains)
            for specimen_identifier, specimen_steps in steps.items():
                if not specimen_identifier in created_specimens:
                    created_specimens[specimen_identifier] = cls._create_specimen(
                        specimen_identifier, steps, created_specimens
                    )
                else:
                    pass
        created_slide_samples = [
            specimen
            for specimen in created_specimens.values()
            if isinstance(specimen, SlideSample)
        ]

        return created_slide_samples, stains

    @classmethod
    def _create_specimen(
        cls,
        specimen_identifier: Union[str, SpecimenIdentifier],
        steps: Dict[Union[str, SpecimenIdentifier], List[PreparationStep]],
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen],
    ) -> Specimen:
        sampled_from_steps = [
            step
            for step in steps[specimen_identifier]
            if isinstance(step, Sampling)
            and step.sample_identifier == specimen_identifier
        ]
        sampled_from_identifiers = []

    @classmethod
    def _merge_specimen(
        cls,
        first_specimen: Specimen,
        steps: Dict[Union[str, SpecimenIdentifier], List[PreparationStep]],
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen],
    ) -> None:
        pass

    @classmethod
    def _parse_step(
        cls, step: SpecimenPreparationStep
    ) -> Tuple[List[PreparationStep], List[SpecimenStainsCode]]:
        steps: List[PreparationStep] = []
        if step.embedding_medium is not None:
            steps.append(Embedding.from_dataset(step))
        if step.fixative is not None:
            steps.append(Fixation.from_dataset(step))

        if isinstance(step.processing_procedure, SpecimenCollection):
            steps.append(Collection.from_dataset(step))
        elif isinstance(step.processing_procedure, SpecimenProcessing):
            steps.append(Processing.from_dataset(step))
        elif isinstance(step.processing_procedure, SpecimenSampling):
            steps.append(Sampling.from_dataset(step))

        stains = []
        if isinstance(step.processing_procedure, SpecimenStaining):
            # TODO support string stains
            stains.extend(
                SpecimenStainsCode(stain.meaning)
                for stain in step.processing_procedure.substances
                if not isinstance(stain, str)
            )
        return steps, stains
