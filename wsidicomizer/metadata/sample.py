import datetime
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union

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
and sampling) the for sub-specimens in the parent the sample was sampeld from, if specified.
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
        if isinstance(identifier, str):
            return identifier, None
        return identifier.to_identifier_and_issuer()


class PreparationStep(metaclass=ABCMeta):
    """A generic preparation step that represents a preparation action that was peformed
    on a specimen."""

    @abstractmethod
    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        raise NotImplementedError()


@dataclass
class Sampling(PreparationStep):
    """The sampling of a specimen into a new specimen."""

    sample_identifier: Union[str, SpecimenIdentifier]
    method: SpecimenSamplingProcedureCode
    sub_sampling: Optional[Iterable[Union[str, SpecimenIdentifier]]] = None
    date_time: Optional[datetime.datetime] = None
    description: Optional[str] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            self.sample_identifier
        )
        parent_identifier, parent_issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
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


@dataclass
class Embedding(PreparationStep):
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


@dataclass
class Fixation(PreparationStep):
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


@dataclass
class SampledFrom:
    specimen: "Specimen"
    sub_sampling: Optional[Iterable[Union[str, SpecimenIdentifier]]] = None


class Specimen(metaclass=ABCMeta):
    """A generic specimen."""

    def __init__(
        self,
        identifier: Union[str, SpecimenIdentifier],
        type: AnatomicPathologySpecimenTypesCode,
        steps: Iterable[PreparationStep],
    ):
        self.identifier = identifier
        self.type = type
        self.steps = list(steps)

    def add(self, step: PreparationStep) -> None:
        if isinstance(step, Collection) and len(self.steps) != 0:
            raise ValueError("A Collection-step must be the first step.")
        self.steps.append(step)

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        """Return complete list of formatted steps for this specimen. If specimen
        is sampled include steps for the parent specimen."""
        steps: List[SpecimenPreparationStep] = []
        if isinstance(self, SampledSpecimen):
            steps.extend(self.get_steps_for_parent())
        steps.extend(step.to_preparation_step(self) for step in self.steps)
        return steps

    def to_preparation_steps_for_sample(
        self, sample_identifier: Union[str, SpecimenIdentifier]
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps in this specimen used for the given sample."""
        steps: List[SpecimenPreparationStep] = []
        if isinstance(self, SampledSpecimen):
            steps.extend(self.get_steps_for_parent())
        steps.extend(
            step.to_preparation_step(self)
            for step in self._get_steps_before_sampling(sample_identifier)
        )
        sampling_step = self._get_sampling_step_for_sample(sample_identifier)
        steps.append(sampling_step.to_preparation_step(self))
        return steps

    def _get_steps_before_sampling(
        self, sample_identifier: Union[str, SpecimenIdentifier]
    ) -> Iterator[PreparationStep]:
        """Return the steps in this specimen that occured before the given sample was
        sampled."""
        for step in self.steps:
            if isinstance(step, Sampling):
                # Break if sampling step for this sample, otherwise skip
                if step.sample_identifier == sample_identifier:
                    break
                continue
            yield step

    def _get_sampling_step_for_sample(
        self, sample_identifier: Union[str, SpecimenIdentifier]
    ) -> Sampling:
        """Return the sampling step for sample."""
        return next(
            step
            for step in self.steps
            if isinstance(step, Sampling)
            and step.sample_identifier == sample_identifier
        )


class SampledSpecimen(Specimen):
    def __init__(
        self,
        identifier: Union[str, SpecimenIdentifier],
        type: AnatomicPathologySpecimenTypesCode,
        sampling_method: SpecimenSamplingProcedureCode,
        sampled_from: Iterable[SampledFrom],
        steps: Iterable[PreparationStep],
        sampling_datetime: Optional[datetime.datetime] = None,
        sampling_description: Optional[str] = None,
    ):
        super().__init__(identifier, type, steps)
        self.sampled_from = sampled_from
        self.sampling_method = sampling_method
        for sampling in self.sampled_from:
            if sampling.sub_sampling is not None:
                if not isinstance(sampling.specimen, SampledSpecimen):
                    raise ValueError(
                        "Can only define sub-sampling for sampled specimens"
                    )
                missing_sub_sampling = sampling.specimen.get_missing_sub_sampling(
                    sampling.sub_sampling
                )
                if missing_sub_sampling is not None:
                    raise ValueError(
                        f"Specimen {sampling.specimen.identifier} was not sampled from "
                        f"given sub-sampling {missing_sub_sampling}"
                    )

            sampling_step = Sampling(
                sample_identifier=self.identifier,
                method=self.sampling_method,
                sub_sampling=sampling.sub_sampling,
                date_time=sampling_datetime,
                description=sampling_description,
            )
            sampling.specimen.add(sampling_step)

    def get_steps_for_parent(self) -> List[SpecimenPreparationStep]:
        """Return formatted steps for the specimen the sample was sampled from."""
        return [
            step
            for sample in self.sampled_from
            for step in sample.specimen.to_preparation_steps_for_sample(self.identifier)
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
        sub_samplings: Optional[Iterable[Union[str, SpecimenIdentifier]]] = None,
    ) -> SampledFrom:
        missing_sub_sampling = self.get_missing_sub_sampling(sub_samplings)
        if missing_sub_sampling is not None:
            raise ValueError(
                "Could not create sampling as specimen was not sampled "
                f"from {missing_sub_sampling}"
            )
        return SampledFrom(self, sub_samplings)

    def get_missing_sub_sampling(
        self, sub_samplings: Optional[Iterable[Union[str, SpecimenIdentifier]]]
    ) -> Optional[Union[str, SpecimenIdentifier]]:
        if sub_samplings is None:
            return None
        sub_sampling_identifiers = [
            sample.specimen.identifier for sample in self.sampled_from
        ]
        try:
            return next(
                sub_sampling
                for sub_sampling in sub_samplings
                if sub_sampling not in sub_sampling_identifiers
            )
        except StopIteration:
            return None


@dataclass
class ExtractedSpecimen(Specimen):
    """A specimen that has been extracted/taken from a patient in some way. Does not
    need to represent the actual first specimen in the collection chain, but should
    represent the first known (i.e. that we have metadata for) specimen in the collection
    chain."""

    identifier: Union[str, SpecimenIdentifier]
    type: AnatomicPathologySpecimenTypesCode
    extraction_method: Optional[SpecimenCollectionProcedureCode] = None
    extraction_datetime: Optional[datetime.datetime] = None
    extraction_description: Optional[str] = None
    steps: List[PreparationStep] = field(default_factory=list)

    def __post_init__(self):
        if self.extraction_method is not None:
            self.steps.insert(
                0,
                Collection(
                    self.extraction_method,
                    self.extraction_datetime,
                    self.extraction_description,
                ),
            )
        super().__init__(identifier=self.identifier, type=self.type, steps=self.steps)

    def sample(self) -> SampledFrom:
        return SampledFrom(self)


@dataclass
class Sample(SampledSpecimen):
    """A specimen that has been sampled from one or more other specimens."""

    identifier: Union[str, SpecimenIdentifier]
    type: AnatomicPathologySpecimenTypesCode
    sampling_method: SpecimenSamplingProcedureCode
    sampled_from: Iterable[SampledFrom]
    sampling_datetime: Optional[datetime.datetime] = None
    sampling_description: Optional[str] = None
    steps: Iterable[PreparationStep] = field(default_factory=list)

    def __post_init__(self):
        super().__init__(
            identifier=self.identifier,
            type=self.type,
            sampling_method=self.sampling_method,
            sampled_from=self.sampled_from,
            steps=self.steps,
            sampling_datetime=self.sampling_datetime,
            sampling_description=self.sampling_description,
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
    sampling_method: SpecimenSamplingProcedureCode
    sampled_from: Iterable[SampledFrom]
    anatomical_sites: Iterable[Code]
    sampling_datetime: Optional[datetime.datetime] = None
    sampling_description: Optional[str] = None
    uid: Optional[UID] = None
    position: Optional[Union[str, SlideSamplePosition]] = None
    steps: List[PreparationStep] = field(init=False, default_factory=list)

    def __post_init__(self):
        super().__init__(
            identifier=self.identifier,
            type=AnatomicPathologySpecimenTypesCode("Slide"),
            sampling_method=self.sampling_method,
            sampled_from=self.sampled_from,
            steps=self.steps,
            sampling_datetime=self.sampling_datetime,
            sampling_description=self.sampling_description,
        )

    def to_description(
        self,
        stains: Optional[Iterable[SpecimenStainsCode]] = None,
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
    def from_dataset(cls, dataset: Dataset) -> "SlideSample":
        raise NotImplementedError()
