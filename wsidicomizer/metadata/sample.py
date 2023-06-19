import datetime
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, List, Optional, Tuple, Union

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


@dataclass
class SpecimenIdentifier:
    identifier: str
    issuer: Optional[str]
    issuer_type: Optional[Union[str, UniversalEntityIDTypeValues]]

    def __eq__(self, other: Any):
        if isinstance(other, str):
            return self.identifier == other and self.issuer is None
        if isinstance(other, SpecimenIdentifier):
            return self.identifier == other.identifier and self.issuer == other.issuer
        return False

    def to_identifier_and_issuer(self) -> Tuple[str, Optional[IssuerOfIdentifier]]:
        if self.issuer is None:
            return self.identifier, None
        return self.identifier, IssuerOfIdentifier(self.issuer, self.issuer_type)

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
    sampling_method: SpecimenSamplingProcedureCode
    parent_subspecimens: Optional[Iterable[Union[str, SpecimenIdentifier]]] = None
    sampling_datetime: Optional[datetime.datetime] = None
    sampling_description: Optional[str] = None

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
                method=self.sampling_method.code,
                parent_specimen_id=parent_identifier,
                parent_specimen_type=specimen.type.code,
                issuer_of_parent_specimen_id=parent_issuer,
            ),
            # processing_datetime=self.sampling_datetime,
            issuer_of_specimen_id=issuer,
            processing_description=self.sampling_description,
        )


@dataclass
class Collection(PreparationStep):
    """The collection of a specimen."""

    extraction_method: SpecimenCollectionProcedureCode
    extraction_datetime: Optional[datetime.datetime] = None
    description: Optional[str] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenCollection(
                procedure=self.extraction_method.code
            ),
            # processing_datetime=self.extraction_datetime,
            issuer_of_specimen_id=issuer,
            processing_description=self.description,
        )


@dataclass
class Processing(PreparationStep):
    """Other processing steps made on a specimen."""

    processing_method: SpecimenPreparationStepsCode
    processing_datetime: Optional[datetime.datetime] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenProcessing(
                description=self.processing_method.code
            ),
            # processing_datetime=self.processing_datetime,
            issuer_of_specimen_id=issuer,
        )


@dataclass
class Embedding(PreparationStep):
    medium: SpecimenEmbeddingMediaCode
    embedding_datetime: Optional[datetime.datetime] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenProcessing(description="Embedding"),
            embedding_medium=self.medium.code,
            # processing_datetime=self.embedding_datetime,
            issuer_of_specimen_id=issuer,
        )


@dataclass
class Fixation(PreparationStep):
    fixative: SpecimenFixativesCode
    fixation_datetime: Optional[datetime.datetime] = None

    def to_preparation_step(self, specimen: "Specimen") -> SpecimenPreparationStep:
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenProcessing(description="Fixation"),
            embedding_medium=self.fixative.code,
            # processing_datetime=self.fixation_datetime,
            issuer_of_specimen_id=issuer,
        )


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
        sampled_from: Iterable[Tuple["Specimen", Optional[Iterable[str]]]],
        steps: Iterable[PreparationStep],
        sampling_datetime: Optional[datetime.datetime] = None,
        sampling_description: Optional[str] = None,
    ):
        super().__init__(identifier, type, steps)
        self.sampled_from = sampled_from
        self.sampling_method = sampling_method
        for (
            parent_specimen,
            parent_specimen_subspecimen_identifiers,
        ) in self.sampled_from:
            if parent_specimen_subspecimen_identifiers is not None:
                if not isinstance(parent_specimen, SampledSpecimen):
                    raise ValueError()
                # Should throw if parent specimen does not have all the sampled from subspecimens
            sampling_step = Sampling(
                sample_identifier=self.identifier,
                sampling_method=self.sampling_method,
                parent_subspecimens=parent_specimen_subspecimen_identifiers,
                sampling_datetime=sampling_datetime,
                sampling_description=sampling_description,
            )
            parent_specimen.add(sampling_step)

    def get_steps_for_parent(self) -> List[SpecimenPreparationStep]:
        """Return formatted steps for the specimen the sample was sampled from."""
        return [
            step
            for parent, _ in self.sampled_from
            for step in parent.to_preparation_steps_for_sample(self.identifier)
        ]


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


@dataclass
class Sample(SampledSpecimen):
    """A specimen that has been sampled from one or more other specimens."""

    identifier: Union[str, SpecimenIdentifier]
    type: AnatomicPathologySpecimenTypesCode
    sampling_method: SpecimenSamplingProcedureCode
    sampled_from: Iterable[Tuple["Specimen", Optional[Iterable[str]]]]
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
class SlideSample(SampledSpecimen):
    identifier: Union[str, SpecimenIdentifier]
    sampling_method: SpecimenSamplingProcedureCode
    sampled_from: Iterable[Tuple["Specimen", Optional[Iterable[str]]]]
    anatomical_sites: Iterable[Code]
    sampling_datetime: Optional[datetime.datetime] = None
    sampling_description: Optional[str] = None
    uid: Optional[UID] = None
    position: Optional[Union[str, Tuple[float, float, float]]] = None
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
        return SpecimenDescription(
            specimen_id=identifier,
            specimen_uid=sample_uid,
            specimen_preparation_steps=sample_preparation_steps,
            specimen_location=self.position,
            primary_anatomic_structures=[
                anatomical_site for anatomical_site in self.anatomical_sites
            ],
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "SlideSample":
        raise NotImplementedError()
