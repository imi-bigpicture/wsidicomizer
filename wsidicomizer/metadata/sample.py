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

import datetime
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union
import logging

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
from highdicom.sr import CodedConcept
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
        """Determine if other specimen identifiers is equal to this."""
        if isinstance(other, str):
            return self.value == other and self.issuer is None
        if isinstance(other, SpecimenIdentifier):
            return self.value == other.value and self.issuer == other.issuer
        return False

    def to_identifier_and_issuer(self) -> Tuple[str, Optional[IssuerOfIdentifier]]:
        """Format into string identifier and IssuerOfIdentifier."""
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

    @classmethod
    def from_sampling(
        cls, sampling: SpecimenSampling
    ) -> Union[str, "SpecimenIdentifier"]:
        # TODO update this for id issuer
        return sampling.parent_specimen_id

    @classmethod
    def from_step(
        cls, step: SpecimenPreparationStep
    ) -> Union[str, "SpecimenIdentifier"]:
        # TODO update this for id issuer
        return step.specimen_id


class PreparationStep(metaclass=ABCMeta):
    """
    Metaclass for a preparation step for a specimen.

    A preparation step is an action performed on a specimen.
    """

    @abstractmethod
    def to_preparation_step(
        self, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        SpecimenPreparationStep:
            Dicom dataset describing the processing step.

        """
        raise NotImplementedError()


@dataclass
class Sampling(PreparationStep):
    """
    The sampling of a specimen into samples that can be used to create new specimens.

    See
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part16/sect_CID_8110.html
    for allowed sampling methods.
    """

    specimen: "Specimen"
    method: SpecimenSamplingProcedureCode
    sampling_chain_constraints: Optional[Sequence["Sampling"]] = None
    date_time: Optional[datetime.datetime] = None
    description: Optional[str] = None

    def to_preparation_step(
        self, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        SpecimenPreparationStep:
            Dicom dataset describing the processing step.

        """
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen_identifier
        )
        parent_identifier, parent_issuer = SpecimenIdentifier.get_identifier_and_issuer(
            self.specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenSampling(
                method=self.method.code,
                parent_specimen_id=parent_identifier,
                parent_specimen_type=self.specimen.type.code,
                issuer_of_parent_specimen_id=parent_issuer,
            ),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
            processing_description=self.description,
        )

    @property
    def index(self) -> int:
        return [step for step in self.specimen.samplings].index(self)

    def to_preparation_steps(
        self, sample_identifier: Union[str, SpecimenIdentifier]
    ) -> List[SpecimenPreparationStep]:
        """Return list of SpecimenPreparationSteps for sampling."""
        steps = self.specimen.to_preparation_steps_for_sampling(self)
        steps.append(self.to_preparation_step(sample_identifier))
        return steps


@dataclass
class Collection(PreparationStep):
    """
    The collection of a specimen from a body.

    See
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part16/sect_CID_8109.html
    for allowed collection methods.
    """

    method: SpecimenCollectionProcedureCode
    date_time: Optional[datetime.datetime] = None
    description: Optional[str] = None

    def to_preparation_step(
        self, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        SpecimenPreparationStep:
            Dicom dataset describing the processing step.

        """
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen_identifier
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
        """Create `Collection` from parsing of a `SpecimenPreparationStep`."""
        assert isinstance(dataset.processing_procedure, SpecimenCollection)
        return cls(
            SpecimenCollectionProcedureCode.from_code_value(
                dataset.processing_procedure.procedure.value
            ),
            # date_time=dataset.processing_datetime,
        )


@dataclass
class Processing(PreparationStep):
    """
    Other processing steps, such as heating or clearing, made on a specimen.

    See
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part16/sect_CID_8113.html
    for allowed proo´cessing methods.
    """

    method: SpecimenPreparationStepsCode
    date_time: Optional[datetime.datetime] = None

    def to_preparation_step(
        self, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        SpecimenPreparationStep:
            Dicom dataset describing the processing step.

        """
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen_identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenProcessing(description=self.method.code),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "Processing":
        """Create `Processing` from parsing of a `SpecimenPreparationStep`."""
        assert isinstance(dataset.processing_procedure, SpecimenProcessing)
        return cls(
            SpecimenPreparationStepsCode.from_code_value(
                dataset.processing_procedure.description.value
            ),
            # date_time=dataset.processing_datetime,
        )


@dataclass
class Embedding(PreparationStep):
    """
    Embedding of a specimen in an medium.

    See
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part16/sect_CID_8115.html
    for allowed mediums.
    """

    medium: SpecimenEmbeddingMediaCode
    date_time: Optional[datetime.datetime] = None

    def to_preparation_step(
        self, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        SpecimenPreparationStep:
            Dicom dataset describing the processing step.

        """
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen_identifier
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
        """Create `Embedding` from parsing of a `SpecimenPreparationStep`."""
        assert dataset.embedding_medium is not None
        return cls(
            SpecimenEmbeddingMediaCode.from_code_value(dataset.embedding_medium.value),
            # date_time=dataset.processing_datetime,
        )


@dataclass
class Fixation(PreparationStep):
    """
    Fixation of a specimen using a fixative.

    See
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part16/sect_CID_8114.html
    for allowed fixatives.
    """

    fixative: SpecimenFixativesCode
    date_time: Optional[datetime.datetime] = None

    def to_preparation_step(
        self, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        SpecimenPreparationStep:
            Dicom dataset describing the processing step.

        """
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen_identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenProcessing(description="Fixation"),
            fixative=self.fixative.code,
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "Fixation":
        """Create `Fixation` from parsing of a `SpecimenPreparationStep`."""
        assert dataset.fixative is not None
        return cls(
            SpecimenFixativesCode.from_code_value(dataset.fixative.value),
            # date_time=dataset.processing_datetime,
        )


@dataclass
class Staining(PreparationStep):
    """
    Staining of a specimen using staining substances.

    The substances can be given either as string or coded values. See
    https://dicom.nema.org/medical/Dicom/current/output/chtml/part16/sect_CID_8112.html
    for allowed stain codes.
    """

    substances: List[Union[str, SpecimenStainsCode]]
    date_time: Optional[datetime.datetime] = None

    def to_preparation_step(
        self, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        SpecimenPreparationStep:
            Dicom dataset describing the processing step.

        """
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            specimen_identifier
        )
        substances: List[Union[str, Code]] = []
        for substance in self.substances:
            if isinstance(substance, str):
                substances.append(substance)
            else:
                substances.append(substance.code)
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenStaining(substances=substances),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> "Staining":
        """Create `Staining` from parsing of a `SpecimenPreparationStep`."""
        assert isinstance(dataset.processing_procedure, SpecimenStaining)
        substances: List[Union[str, SpecimenStainsCode]] = []
        for substance in dataset.processing_procedure.substances:
            if isinstance(substance, CodedConcept):
                substances.append(SpecimenStainsCode.from_code_value(substance.value))
            elif isinstance(substance, str):
                substances.append(substance)
            else:
                raise TypeError(
                    f"Unknown type {type(substance)} for substance {substance}."
                )
        return cls(
            substances,
            # date_time=dataset.processing_datetime,
        )


class Specimen(metaclass=ABCMeta):
    """Metaclass for a specimen."""

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
        return [step.to_preparation_step(self.identifier) for step in self.steps]

    def to_preparation_steps_for_sampling(
        self, sampling: Sampling
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps in this specimen used for the given sampling."""
        return [
            step.to_preparation_step(self.identifier)
            for step in self._get_steps_before_sampling(sampling)
        ]

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


class SampledSpecimen(Specimen, metaclass=ABCMeta):
    """Metaclass for a specimen thas has been sampled from one or more specimens."""

    def __init__(
        self,
        identifier: Union[str, SpecimenIdentifier],
        type: AnatomicPathologySpecimenTypesCode,
        sampled_from: Optional[Union[Sampling, Sequence[Sampling]]],
        steps: Sequence[PreparationStep],
    ):
        super().__init__(identifier, type, steps)
        if sampled_from is None:
            sampled_from = []
        elif isinstance(sampled_from, Sampling):
            sampled_from = [sampled_from]
        elif not isinstance(sampled_from, list):
            sampled_from = list(sampled_from)
        self._sampled_from = sampled_from

    def add(self, step: PreparationStep) -> None:
        if isinstance(step, Collection):
            raise ValueError(
                "A collection step can only be added to specimens of type `ExtractedSpecimen`"
            )
        self.steps.append(step)

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        """Return complete list of formatted steps for this specimen. If specimen
        is sampled include steps for the sampled specimen."""
        steps = self._get_steps_for_sampling()
        steps.extend(super().to_preparation_steps())
        return steps

    def to_preparation_steps_for_sampling(
        self, sampling: Sampling
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps in this specimen used for the given sampling."""
        steps = self._get_steps_for_sampling(sampling.sampling_chain_constraints)
        steps.extend(super().to_preparation_steps_for_sampling(sampling))
        return steps

    def _get_steps_for_sampling(
        self, sampling_chain_constraints: Optional[Sequence[Sampling]] = None
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps for the specimen the sample was sampled from."""

        return [
            step
            for sampling in self._sampled_from
            if sampling_chain_constraints is None
            or sampling in sampling_chain_constraints
            for step in sampling.to_preparation_steps(self.identifier)
        ]

    def get_samplings(self) -> Dict[Union[str, SpecimenIdentifier], Specimen]:
        """Return a dictionary containing this specimen and all recursive sampled specimens."""
        samplings: Dict[Union[str, SpecimenIdentifier], Specimen] = {
            self.identifier: self
        }
        for sampling in self._sampled_from:
            if not isinstance(sampling.specimen, SampledSpecimen):
                samplings.update({sampling.specimen.identifier: sampling.specimen})
            else:
                samplings.update(sampling.specimen.get_samplings())
        return samplings

    def _check_sampling_constraints(
        self, constraints: Optional[Sequence[Sampling]]
    ) -> None:
        if constraints is None:
            return

        def recursive_search(sampling: Sampling, specimen: Specimen) -> bool:
            """Recursively search for sampling in samplings for specimen."""
            if sampling in specimen.samplings:
                return True
            if isinstance(specimen, SampledSpecimen):
                return any(
                    recursive_search(sampling, sampling.specimen)
                    for sampling in specimen._sampled_from
                )
            return False

        for constraint in constraints:
            if not recursive_search(constraint, self):
                raise ValueError(
                    "Could not create sampling as specimen was not sampled "
                    f"from {constraint}"
                )


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
            # Add self.extraction step as first in list of steps
            self.steps.insert(
                0,
                self.extraction_step,
            )
        else:
            # If extraction step in steps, set it as self.extraction_step
            extraction_step = next(
                (step for step in self.steps if isinstance(step, Collection)), None
            )
            if extraction_step is not None:
                self.extraction_step = extraction_step
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

    def sample(
        self,
        method: SpecimenSamplingProcedureCode,
        date_time: Optional[datetime.datetime] = None,
        description: Optional[str] = None,
        sampling_chain_constraints: Optional[Sequence[Sampling]] = None,
    ) -> Sampling:
        """Create a sampling from the specimen that can be used to create a new sample."""
        self._check_sampling_constraints(sampling_chain_constraints)
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
    steps: List[PreparationStep] = field(default_factory=list)

    def __post_init__(self):
        super().__init__(
            identifier=self.identifier,
            type=AnatomicPathologySpecimenTypesCode("Slide"),
            sampled_from=self.sampled_from,
            steps=self.steps,
        )

    def to_description(
        self,
        stains: Optional[Sequence[Staining]] = None,
    ) -> SpecimenDescription:
        """Create a formatted specimen description for the specimen."""
        if stains is None:
            stains = []
        sample_uid = generate_uid() if self.uid is None else self.uid
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        sample_preparation_steps.extend(self.to_preparation_steps())
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            self.identifier
        )
        for stain in stains:
            step = stain.to_preparation_step(self.identifier)
            sample_preparation_steps.append(step)
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
        cls, specimen_description_datasets: Iterable[Dataset]
    ) -> Tuple[Optional[List["SlideSample"]], Optional[List[Staining]]]:
        """
        Parse Specimen Description Sequence in dataset into SlideSamples and Stainings.

        Parameters
        ----------
        dataset: Dataset
            Dataset with Specimen Description Sequence to parse.

        Returns
        ----------
        Optional[Tuple[List["SlideSample"], List[Staining]]]
            SlideSamples and Stainings parsed from dataset, or None if no or invalid
            Specimen Description Sequence.

        """
        try:
            descriptions = [
                SpecimenDescription.from_dataset(specimen_description_dataset)
                for specimen_description_dataset in specimen_description_datasets
            ]
        except (AttributeError, ValueError) as exception:
            logging.warn("Failed to parse SpecimenDescriptionSequence", exception)
            return None, None
        created_specimens: Dict[
            Union[str, SpecimenIdentifier], Union[ExtractedSpecimen, Sample]
        ] = {}
        slide_samples: List[SlideSample] = []
        stainings: List[Staining] = []
        for description in descriptions:
            slide_sample = cls._create_slide_sample(
                description, created_specimens, stainings
            )
            slide_samples.append(slide_sample)

        return slide_samples, stainings

    @classmethod
    def _parse_preparation_steps_for_specimen(
        cls,
        identifier: Union[str, SpecimenIdentifier],
        steps_by_identifier: Dict[
            Union[str, SpecimenIdentifier], List[Optional[SpecimenPreparationStep]]
        ],
        existing_specimens: Dict[
            Union[str, SpecimenIdentifier], Union[ExtractedSpecimen, Sample]
        ],
        stop_at_step: Optional[SpecimenPreparationStep] = None,
    ) -> Tuple[List[PreparationStep], List[Sampling]]:
        """
        Parse PreparationSteps and Samplings for a specimen.

        Creates or updates parent specimens.

        Parameters
        ----------
        identifier: Union[str, SpecimenIdentifier]
            The identifier of the specimen to parse.
        steps_by_identifier: Dict[
            Union[str, SpecimenIdentifier], List[Optional[SpecimenPreparationStep]]
        ]
            SpecimenPreparationSteps ordered by specimen identifier.
        existing_specimens: Dict[
            Union[str, SpecimenIdentifier], Union[ExtractedSpecimen, Sample]
        ]
            Existing specimens ordered by specimen identifier.
        stop_at_step: SpecimenPreparationStep
            SpecimenSampling step in the list of steps for this identifier at which the
            list should not be processed further.

        Returns
        ----------
        Tuple[List[PreparationStep], List[Sampling]]
            Parsed PreparationSteps and Samplings for the specimen.

        """
        if stop_at_step is not None:
            procedure = stop_at_step.processing_procedure
            if (
                not isinstance(procedure, SpecimenSampling)
                or SpecimenIdentifier.from_sampling(procedure) != identifier
            ):
                raise ValueError(
                    "Stop at step should be a parent SpecimenSampling step  ."
                )

        samplings: List[Sampling] = []
        preparation_steps: List[PreparationStep] = []

        for index, step in enumerate(steps_by_identifier[identifier]):
            if stop_at_step is not None and stop_at_step == step:
                # We should not parse the rest of the list
                break
            if step is None:
                # This step has already been parsed, skip to next.
                continue
            if step.specimen_id != identifier:
                # This is OK if SpecimenSampling with matching parent identifier
                if (
                    not isinstance(step.processing_procedure, SpecimenSampling)
                    or SpecimenIdentifier.from_sampling(step.processing_procedure)
                    != identifier
                ):
                    error = (
                        f"Got step of unexpected type {type(step.processing_procedure)}"
                        f"or identifier {step.specimen_id} for specimen {identifier}"
                    )
                    raise ValueError(error)
                # Skip to next
                continue

            procedure = step.processing_procedure
            if isinstance(procedure, SpecimenStaining):
                # Stainings are handled elsewhere
                pass
            elif isinstance(procedure, SpecimenCollection):
                any_sampling_steps = any(
                    sampling_step
                    for sampling_step in steps_by_identifier[identifier]
                    if sampling_step is not None
                    and isinstance(sampling_step.processing_procedure, SpecimenSampling)
                    and sampling_step.specimen_id == identifier
                )
                if index != 0 or any_sampling_steps:
                    raise ValueError(
                        (
                            "Collection step should be first step and there should not "
                            "be any sampling steps."
                        )
                    )
                preparation_steps.append(Collection.from_dataset(step))
            elif isinstance(procedure, SpecimenProcessing):
                if not isinstance(procedure.description, str):
                    # Only coded processing procedure descriptions are supported
                    # String descriptions could be used for fixation or embedding steps,
                    # those are parsed separately.
                    preparation_steps.append(Processing.from_dataset(step))
            elif isinstance(procedure, SpecimenSampling):
                parent_identifier = SpecimenIdentifier.from_sampling(procedure)
                if parent_identifier in existing_specimens:
                    # Parent already exists. Parse any non-parsed steps
                    parent = existing_specimens[parent_identifier]
                    (
                        parent_steps,
                        sampling_constraints,
                    ) = cls._parse_preparation_steps_for_specimen(
                        parent_identifier, steps_by_identifier, existing_specimens, step
                    )
                    for parent_step in parent_steps:
                        # Only add step if an equivalent does not exists
                        if not any(step == parent_step for step in parent.steps):
                            parent.add(parent_step)
                    if isinstance(parent, Sample):
                        parent._sampled_from.extend(sampling_constraints)
                else:
                    # Need to create parent
                    parent_type = AnatomicPathologySpecimenTypesCode.from_code_value(
                        procedure.parent_specimen_type.value
                    )
                    parent = cls._create_specimen(
                        parent_identifier,
                        parent_type,
                        steps_by_identifier,
                        existing_specimens,
                        step,
                    )
                    if isinstance(parent, Sample):
                        sampling_constraints = parent._sampled_from
                    else:
                        sampling_constraints = None
                    existing_specimens[parent_identifier] = parent

                # TODO is this assert needed?
                if isinstance(parent, Sample):
                    # If Sample create sampling with constraint
                    sampling = parent.sample(
                        SpecimenSamplingProcedureCode.from_code_value(
                            procedure.method.value
                        ),
                        sampling_chain_constraints=sampling_constraints,
                    )
                else:
                    # Extracted specimen can not have constraint
                    sampling = parent.sample(
                        SpecimenSamplingProcedureCode.from_code_value(
                            procedure.method.value
                        ),
                    )

                samplings.append(sampling)
            else:
                raise NotImplementedError(f"Step of type {type(procedure)}")
            if step.fixative is not None:
                preparation_steps.append(Fixation.from_dataset(step))
            if step.embedding_medium is not None:
                preparation_steps.append(Embedding.from_dataset(step))

            # Clear this step so that it will not be processed again
            steps_by_identifier[identifier][index] = None
        return preparation_steps, samplings

    @classmethod
    def _create_specimen(
        cls,
        identifier: Union[str, SpecimenIdentifier],
        specimen_type: AnatomicPathologySpecimenTypesCode,
        steps_by_identifier: Dict[
            Union[str, SpecimenIdentifier], List[Optional[SpecimenPreparationStep]]
        ],
        existing_specimens: Dict[
            Union[str, SpecimenIdentifier], Union[ExtractedSpecimen, Sample]
        ],
        stop_at_step: SpecimenPreparationStep,
    ) -> Union[ExtractedSpecimen, Sample]:
        """
        Create an ExtractedSpecimen or Sample.

        Parameters
        ----------
        identifier: Union[str, SpecimenIdentifier]
            The identifier of the specimen to create.
        specimen_type: AnatomicPathologySpecimenTypesCode
            The coded type of the specimen to create.
        steps_by_identifier: Dict[
            Union[str, SpecimenIdentifier], List[Optional[SpecimenPreparationStep]]
        ]
            SpecimenPreparationSteps ordered by specimen identifier.
        existing_specimens: Dict[
            Union[str, SpecimenIdentifier], Union[ExtractedSpecimen, Sample]
        ]
            Existing specimens ordered by specimen identifier.
        stop_at_step: SpecimenPreparationStep
            Stop processing steps for this specimen at this step in the list.

        Returns
        ----------
        Union[ExtractedSpecimen, Sample]
            Created ExtracedSpecimen, if the specimen has no parents, or Specimen.

        """
        logging.debug(f"Creating specimen with identifier {identifier}")
        preparation_steps, samplings = cls._parse_preparation_steps_for_specimen(
            identifier, steps_by_identifier, existing_specimens, stop_at_step
        )

        if len(samplings) == 0:
            return ExtractedSpecimen(
                identifier=identifier,
                type=specimen_type,
                steps=preparation_steps,
            )
        return Sample(
            identifier=identifier,
            type=specimen_type,
            sampled_from=samplings,
            steps=preparation_steps,
        )

    @classmethod
    def _create_slide_sample(
        cls,
        description: SpecimenDescription,
        existing_specimens: Dict[
            Union[str, SpecimenIdentifier], Union[ExtractedSpecimen, Sample]
        ],
        existing_stainings: List[Staining],
    ) -> "SlideSample":
        """
        Create a SlideSample from Specimen Description.

        Contained parent specimens and stainings are created or updated.

        Parameters
        ----------
        description: SpecimenDescription
            Specimen Description to parse.
        existing_specimens: Dict[
            Union[str, SpecimenIdentifier], Union[ExtractedSpecimen, Sample]
        ]
            Dictionary with existing specimens. New/updated specimens this Specimen
            Description are updated/added.
        existing_stainings: List[Staining]
            List of existing stainings. New stainings from this Specimen Description are
            added.

        Returns
        ----------
        SlideSample
            Parsed SlideSample.

        """
        # Sort the steps based on specimen identifier.
        # Sampling steps are put into to both sampled and parent bucket.
        steps_by_identifier: Dict[
            Union[str, SpecimenIdentifier], List[Optional[SpecimenPreparationStep]]
        ] = defaultdict(list)

        for step in description.specimen_preparation_steps:
            if isinstance(step.processing_procedure, SpecimenStaining):
                staining = Staining.from_dataset(step)
                if not any(staining == existing for existing in existing_stainings):
                    existing_stainings.append(staining)
            elif isinstance(step.processing_procedure, SpecimenSampling):
                parent_identifier = SpecimenIdentifier.from_sampling(
                    step.processing_procedure
                )
                steps_by_identifier[parent_identifier].append(step)
            identifier = SpecimenIdentifier.from_step(step)
            steps_by_identifier[identifier].append(step)

        identifier = SpecimenIdentifier.from_step(
            description.specimen_preparation_steps[-1]
        )

        preparation_steps, samplings = cls._parse_preparation_steps_for_specimen(
            identifier, steps_by_identifier, existing_specimens
        )

        if len(samplings) > 1:
            raise ValueError("Should be max one sampling, got.", len(samplings))
        # TODO add position when highdicom support
        return cls(
            identifier=identifier,
            anatomical_sites=[],
            sampled_from=next(iter(samplings), None),
            uid=UID(description.SpecimenUID),
            # position=
            steps=preparation_steps,
        )
