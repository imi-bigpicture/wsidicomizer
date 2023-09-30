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

from abc import ABCMeta
from collections import defaultdict
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union
import logging

from highdicom import (
    SpecimenCollection,
    SpecimenDescription,
    SpecimenPreparationStep,
    SpecimenProcessing,
    SpecimenSampling,
    SpecimenStaining,
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
    SlideSamplePosition,
    Specimen,
    SpecimenIdentifier,
    Staining,
)


class SpecimenIdentifierDicom:
    """A specimen identifier including an optional issuer."""

    @classmethod
    def from_sampling(
        cls, sampling: SpecimenSampling
    ) -> Union[str, SpecimenIdentifier]:
        # TODO update this for id issuer
        return sampling.parent_specimen_id

    @classmethod
    def from_step(cls, step: SpecimenPreparationStep) -> Union[str, SpecimenIdentifier]:
        # TODO update this for id issuer
        return step.specimen_id


class PreparationStepDicom(metaclass=ABCMeta):
    @classmethod
    def to_dataset(
        cls, step: PreparationStep, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        step: Sampling
            Step to convert into dataset.
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        SpecimenPreparationStep:
            Dicom dataset describing the processing step.

        """
        if isinstance(step, Sampling):
            return SamplingDicom.to_dataset(step, specimen_identifier)
        if isinstance(step, Collection):
            return CollectionDicom.to_dataset(step, specimen_identifier)
        if isinstance(step, Processing):
            return ProcessingDicom.to_dataset(step, specimen_identifier)
        if isinstance(step, Embedding):
            return EmbeddingDicom.to_dataset(step, specimen_identifier)
        if isinstance(step, Fixation):
            return FixationDicom.to_dataset(step, specimen_identifier)
        if isinstance(step, Staining):
            return StainingDicom.to_dataset(step, specimen_identifier)
        raise NotImplementedError()


class SamplingDicom(PreparationStepDicom):
    @classmethod
    def to_dataset(
        cls, sampling: Sampling, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        sampling: Sampling
            Step to convert into dataset.
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
            sampling.specimen.identifier
        )
        return SpecimenPreparationStep(
            specimen_id=identifier,
            processing_procedure=SpecimenSampling(
                method=sampling.method.code,
                parent_specimen_id=parent_identifier,
                parent_specimen_type=sampling.specimen.type.code,
                issuer_of_parent_specimen_id=parent_issuer,
            ),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
            processing_description=sampling.description,
        )

    @classmethod
    def to_datasets(
        cls, sampling: Sampling, sample_identifier: Union[str, SpecimenIdentifier]
    ) -> List[SpecimenPreparationStep]:
        """Return list of Dicom datasets for the sampling.

        Parameters
        ----------
        sampling: Sampling
            Step to convert into dataset.
        specimen_identifier: Union[str, SpecimenIdentifier]:
            Identifier for the specimen that was processed.

        Parameters
        ----------
        List[SpecimenPreparationStep]:
            Dicom datasets describing the sampling step.
        """
        steps = SpecimenDicom.to_datasets_for_sampling(sampling.specimen, sampling)
        steps.append(cls.to_dataset(sampling, sample_identifier))
        return steps


class CollectionDicom(PreparationStepDicom):
    @classmethod
    def to_dataset(
        cls,
        collection: Collection,
        specimen_identifier: Union[str, SpecimenIdentifier],
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        collection: Collection
            Step to convert into dataset.
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
            processing_procedure=SpecimenCollection(procedure=collection.method.code),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
            processing_description=collection.description,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> Collection:
        """Create `Collection` from parsing of a `SpecimenPreparationStep`."""
        assert isinstance(dataset.processing_procedure, SpecimenCollection)
        return Collection(
            SpecimenCollectionProcedureCode.from_code_value(
                dataset.processing_procedure.procedure.value
            ),
            # date_time=dataset.processing_datetime,
        )


class ProcessingDicom(PreparationStepDicom):
    @classmethod
    def to_dataset(
        cls,
        processing: Processing,
        specimen_identifier: Union[str, SpecimenIdentifier],
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        processing: Processing
            Step to convert into dataset.
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
            processing_procedure=SpecimenProcessing(description=processing.method.code),
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> Processing:
        """Create `Processing` from parsing of a `SpecimenPreparationStep`."""
        assert isinstance(dataset.processing_procedure, SpecimenProcessing)
        return Processing(
            SpecimenPreparationStepsCode.from_code_value(
                dataset.processing_procedure.description.value
            ),
            # date_time=dataset.processing_datetime,
        )


class EmbeddingDicom(PreparationStepDicom):
    @classmethod
    def to_dataset(
        cls, embedding: Embedding, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        embedding: Embedding
            Step to convert into dataset.
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
            embedding_medium=embedding.medium.code,
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> Embedding:
        """Create `Embedding` from parsing of a `SpecimenPreparationStep`."""
        assert dataset.embedding_medium is not None
        return Embedding(
            SpecimenEmbeddingMediaCode.from_code_value(dataset.embedding_medium.value),
            # date_time=dataset.processing_datetime,
        )


class FixationDicom(PreparationStepDicom):
    @classmethod
    def to_dataset(
        cls, fixation: Fixation, specimen_identifier: Union[str, SpecimenIdentifier]
    ) -> SpecimenPreparationStep:
        """Return Dicom dataset for the step.

        Parameters
        ----------
        fixation: Fixation
            Step to convert into dataset.
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
            fixative=fixation.fixative.code,
            # processing_datetime=self.date_time,
            issuer_of_specimen_id=issuer,
        )

    @classmethod
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> Fixation:
        """Create `Fixation` from parsing of a `SpecimenPreparationStep`."""
        assert dataset.fixative is not None
        return Fixation(
            SpecimenFixativesCode.from_code_value(dataset.fixative.value),
            # date_time=dataset.processing_datetime,
        )


class StainingDicom(PreparationStepDicom):
    @classmethod
    def to_dataset(
        cls, staining: Staining, specimen_identifier: Union[str, SpecimenIdentifier]
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
        for substance in staining.substances:
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
    def from_dataset(cls, dataset: SpecimenPreparationStep) -> Staining:
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
        return Staining(
            substances,
            # date_time=dataset.processing_datetime,
        )


class SpecimenDicom(metaclass=ABCMeta):
    """Metaclass for a specimen."""

    @classmethod
    def to_datasets(cls, specimen: Specimen) -> List[SpecimenPreparationStep]:
        """Return complete list of formatted steps for this specimen. If specimen
        is sampled include steps for the sampled specimen."""
        if isinstance(specimen, SampledSpecimen):
            return SampledSpecimenDicom.to_datasets(specimen)
        if isinstance(specimen, ExtractedSpecimen):
            return ExtractedSpecimenDicom.to_datasets(specimen)
        raise NotImplementedError()

    @classmethod
    def to_datasets_for_sampling(
        cls, specimen: Specimen, sampling: Sampling
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps in this specimen used for the given sampling."""
        if isinstance(specimen, SampledSpecimen):
            return SampledSpecimenDicom.to_datasets_for_sampling(specimen, sampling)
        if isinstance(specimen, ExtractedSpecimen):
            return ExtractedSpecimenDicom.to_datasets_for_sampling(specimen, sampling)
        raise NotImplementedError()

    @classmethod
    def _get_steps_before_sampling(
        cls, specimen: Specimen, sampling: Sampling
    ) -> Iterator[PreparationStep]:
        """Return the steps in this specimen that occurred before the given sampling."""
        for step in specimen.steps:
            if isinstance(step, Sampling):
                # Break if sampling step for this sample, otherwise skip
                if step == sampling:
                    break
                continue
            yield step


class SampledSpecimenDicom(SpecimenDicom, metaclass=ABCMeta):
    """Metaclass for a specimen thas has been sampled from one or more specimens."""

    @classmethod
    def to_datasets(cls, specimen: SampledSpecimen) -> List[SpecimenPreparationStep]:
        """Return complete list of formatted steps for this specimen. If specimen
        is sampled include steps for the sampled specimen."""
        steps = cls._get_steps_for_sampling(specimen)
        steps.extend(
            PreparationStepDicom.to_dataset(step, specimen.identifier)
            for step in specimen.steps
        )
        return steps

    @classmethod
    def to_datasets_for_sampling(
        cls, specimen: SampledSpecimen, sampling: Sampling
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps in this specimen used for the given sampling."""
        steps = cls._get_steps_for_sampling(
            specimen, sampling.sampling_chain_constraints
        )
        steps.extend(
            PreparationStepDicom.to_dataset(step, specimen.identifier)
            for step in cls._get_steps_before_sampling(specimen, sampling)
        )
        return steps

    @classmethod
    def _get_steps_for_sampling(
        cls,
        specimen: SampledSpecimen,
        sampling_chain_constraints: Optional[Sequence[Sampling]] = None,
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps for the specimen the sample was sampled from."""

        return [
            step
            for sampling in specimen._sampled_from
            if sampling_chain_constraints is None
            or sampling in sampling_chain_constraints
            for step in SamplingDicom.to_datasets(sampling, specimen.identifier)
        ]


class ExtractedSpecimenDicom(SpecimenDicom):
    @classmethod
    def to_datasets(cls, specimen: ExtractedSpecimen) -> List[SpecimenPreparationStep]:
        """Return complete list of formatted steps for this specimen. If specimen
        is sampled include steps for the sampled specimen."""
        return [
            PreparationStepDicom.to_dataset(step, specimen.identifier)
            for step in specimen.steps
        ]

    @classmethod
    def to_datasets_for_sampling(
        cls, specimen: ExtractedSpecimen, sampling: Sampling
    ) -> List[SpecimenPreparationStep]:
        """Return formatted steps in this specimen used for the given sampling."""
        return [
            PreparationStepDicom.to_dataset(step, specimen.identifier)
            for step in cls._get_steps_before_sampling(specimen, sampling)
        ]


class SlideSampleDicom(SampledSpecimenDicom):
    """A sample that has been placed on a slide."""

    @classmethod
    def to_dataset(
        cls,
        slide_sample: SlideSample,
        stains: Optional[Sequence[Staining]] = None,
    ) -> SpecimenDescription:
        """Create a formatted specimen description for the specimen."""
        if stains is None:
            stains = []
        sample_uid = generate_uid() if slide_sample.uid is None else slide_sample.uid
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        sample_preparation_steps.extend(cls.to_datasets(slide_sample))
        identifier, issuer = SpecimenIdentifier.get_identifier_and_issuer(
            slide_sample.identifier
        )
        for stain in stains:
            step = StainingDicom.to_dataset(stain, slide_sample.identifier)
            sample_preparation_steps.append(step)
        if isinstance(slide_sample.position, str):
            position = slide_sample.position
        elif isinstance(slide_sample.position, SlideSamplePosition):
            position = slide_sample.position.to_tuple()
        else:
            position = None
        return SpecimenDescription(
            specimen_id=identifier,
            specimen_uid=sample_uid,
            specimen_preparation_steps=sample_preparation_steps,
            specimen_location=position,
            primary_anatomic_structures=[
                anatomical_site for anatomical_site in slide_sample.anatomical_sites
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
                or SpecimenIdentifierDicom.from_sampling(procedure) != identifier
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
                    or SpecimenIdentifierDicom.from_sampling(step.processing_procedure)
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
                preparation_steps.append(CollectionDicom.from_dataset(step))
            elif isinstance(procedure, SpecimenProcessing):
                if not isinstance(procedure.description, str):
                    # Only coded processing procedure descriptions are supported
                    # String descriptions could be used for fixation or embedding steps,
                    # those are parsed separately.
                    preparation_steps.append(ProcessingDicom.from_dataset(step))
            elif isinstance(procedure, SpecimenSampling):
                parent_identifier = SpecimenIdentifierDicom.from_sampling(procedure)
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
                preparation_steps.append(FixationDicom.from_dataset(step))
            if step.embedding_medium is not None:
                preparation_steps.append(EmbeddingDicom.from_dataset(step))

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
    ) -> SlideSample:
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
                staining = StainingDicom.from_dataset(step)
                if not any(staining == existing for existing in existing_stainings):
                    existing_stainings.append(staining)
            elif isinstance(step.processing_procedure, SpecimenSampling):
                parent_identifier = SpecimenIdentifierDicom.from_sampling(
                    step.processing_procedure
                )
                steps_by_identifier[parent_identifier].append(step)
            identifier = SpecimenIdentifierDicom.from_step(step)
            steps_by_identifier[identifier].append(step)

        identifier = SpecimenIdentifierDicom.from_step(
            description.specimen_preparation_steps[-1]
        )

        preparation_steps, samplings = cls._parse_preparation_steps_for_specimen(
            identifier, steps_by_identifier, existing_specimens
        )

        if len(samplings) > 1:
            raise ValueError("Should be max one sampling, got.", len(samplings))
        # TODO add position when highdicom support
        return SlideSample(
            identifier=identifier,
            anatomical_sites=[],
            sampled_from=next(iter(samplings), None),
            uid=UID(description.SpecimenUID),
            # position=
            steps=preparation_steps,
        )
