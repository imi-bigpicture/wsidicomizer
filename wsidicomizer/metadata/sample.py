"""Models for samples."""
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple, Union
from dataclasses_json import dataclass_json

from highdicom import (
    SpecimenCollection,
    SpecimenPreparationStep,
    SpecimenProcessing,
    SpecimenSampling,
)
from pydicom.sr.coding import Code
from pydicom.uid import UID
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationProcedureCode,
    SpecimenSamplingProcedureCode,
)
from wsidicomizer.metadata.fields import FieldFactory


@dataclass_json
class Sample(metaclass=ABCMeta):
    identifier: str
    type: AnatomicPathologySpecimenTypesCode
    anatomical_sites: Iterable[Code] = FieldFactory.list_code_field()
    uid: Optional[UID] = None

    @abstractmethod
    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        raise NotImplementedError()

    def to_sampling_step(
        self, sampling_method: SpecimenSamplingProcedureCode
    ) -> SpecimenSampling:
        return SpecimenSampling(
            method=sampling_method.code,
            parent_specimen_id=self.identifier,
            parent_specimen_type=self.type.code,
        )


@dataclass
class Specimen(Sample):
    """A specimen that has been extracted from a patient."""

    identifier: str
    type: AnatomicPathologySpecimenTypesCode = FieldFactory.concept_code_field(
        AnatomicPathologySpecimenTypesCode,
        AnatomicPathologySpecimenTypesCode("Gross specimen"),
    )
    extraction_method: Optional[
        SpecimenCollectionProcedureCode
    ] = FieldFactory.concept_code_field(SpecimenCollectionProcedureCode)
    fixation_type: Optional[SpecimenFixativesCode] = FieldFactory.concept_code_field(
        SpecimenFixativesCode
    )
    anatomical_sites: Iterable[Code] = FieldFactory.list_code_field()
    uid: Optional[UID] = None

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        steps = []
        if self.extraction_method is not None:
            specimen_sampling_step = SpecimenPreparationStep(
                self.identifier,
                processing_procedure=SpecimenCollection(
                    procedure=self.extraction_method.code,
                ),
            )
            steps.append(specimen_sampling_step)
        if self.fixation_type is not None:
            specimen_preparation_step = SpecimenPreparationStep(
                specimen_id=self.identifier,
                processing_procedure=SpecimenProcessing(
                    SpecimenPreparationProcedureCode("Specimen processing").code
                ),
                fixative=self.fixation_type.code,
            )
            steps.append(specimen_preparation_step)
        return steps


@dataclass_json
@dataclass
class SampledSpecimen:
    """The sampling of a specimen using a sampling method."""

    specimen: Specimen
    sampling_method: Optional[
        SpecimenSamplingProcedureCode
    ] = FieldFactory.concept_code_field(SpecimenSamplingProcedureCode)


@dataclass
class Block(Sample):
    """A block that has been sampled from one or more specimens."""

    identifier: str
    type: AnatomicPathologySpecimenTypesCode = FieldFactory.concept_code_field(
        AnatomicPathologySpecimenTypesCode,
        AnatomicPathologySpecimenTypesCode("Gross specimen"),
    )
    embedding_medium: Optional[
        SpecimenEmbeddingMediaCode
    ] = FieldFactory.concept_code_field(SpecimenEmbeddingMediaCode)
    specimens: Iterable[SampledSpecimen] = field(default_factory=list)
    uid: Optional[UID] = None

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        for sampled_specimen in self.specimens:
            if sampled_specimen.sampling_method is None:
                sampling_method = SpecimenSamplingProcedureCode("Dissection")
            else:
                sampling_method = sampled_specimen.sampling_method
            sample_preparation_steps.extend(
                sampled_specimen.specimen.to_preparation_steps()
            )
            block_sampling_step = SpecimenPreparationStep(
                self.identifier,
                processing_procedure=SpecimenSampling(
                    method=sampling_method.code,
                    parent_specimen_id=sampled_specimen.specimen.identifier,
                    parent_specimen_type=sampled_specimen.specimen.type.code,
                ),
            )
            sample_preparation_steps.append(block_sampling_step)
        if self.embedding_medium is not None:
            block_preparation_step = SpecimenPreparationStep(
                specimen_id=self.identifier,
                processing_procedure=SpecimenProcessing(
                    SpecimenPreparationProcedureCode("Specimen processing").code
                ),
                embedding_medium=self.embedding_medium.code,
            )
            sample_preparation_steps.append(block_preparation_step)
        return sample_preparation_steps

    @property
    def anatomical_sites(self) -> List[Code]:
        return [
            anatomical_site
            for specimen in self.specimens
            for anatomical_site in specimen.specimen.anatomical_sites
        ]


@dataclass
class SimpleSample(Sample):
    """Sample sampled with optional attributes."""

    identifier: str
    type: AnatomicPathologySpecimenTypesCode = FieldFactory.concept_code_field(
        AnatomicPathologySpecimenTypesCode
    )
    embedding_medium: Optional[
        SpecimenEmbeddingMediaCode
    ] = FieldFactory.concept_code_field(SpecimenEmbeddingMediaCode)
    fixative: Optional[SpecimenFixativesCode] = FieldFactory.concept_code_field(
        SpecimenFixativesCode
    )
    specimen_id: Optional[str] = None
    specimen_type: Optional[
        AnatomicPathologySpecimenTypesCode
    ] = FieldFactory.concept_code_field(AnatomicPathologySpecimenTypesCode)
    specimen_sampling_method: Optional[
        SpecimenSamplingProcedureCode
    ] = FieldFactory.concept_code_field(SpecimenSamplingProcedureCode)
    anatomical_sites: Optional[Iterable[Code]] = FieldFactory.list_code_field()
    uid: Optional[UID] = None

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        sample_preparation_steps: List[SpecimenPreparationStep] = []

        if (
            self.specimen_id is not None
            and self.specimen_sampling_method is not None
            and self.specimen_type is not None
        ):
            sample_sampling_step = SpecimenPreparationStep(
                specimen_id=self.identifier,
                processing_procedure=SpecimenSampling(
                    method=self.specimen_sampling_method.code,
                    parent_specimen_id=self.specimen_id,
                    parent_specimen_type=self.specimen_type.code,
                ),
            )
            sample_preparation_steps.append(sample_sampling_step)
        if self.embedding_medium is not None:
            embedding_medium = self.embedding_medium.code
        else:
            embedding_medium = None
        if self.fixative is not None:
            fixative = self.fixative.code
        else:
            fixative = None
        if embedding_medium is not None or fixative is not None:
            preparation_step = SpecimenPreparationStep(
                specimen_id=self.identifier,
                processing_procedure=SpecimenProcessing(
                    SpecimenPreparationProcedureCode("Specimen processing").code
                ),
                embedding_medium=embedding_medium,
                fixative=fixative,
            )
            sample_preparation_steps.append(preparation_step)

        return sample_preparation_steps


@dataclass_json
@dataclass
class SlideSample:
    """Sample sampled using method and place at position on slide."""

    sample: Sample
    sampling_method: Optional[
        SpecimenSamplingProcedureCode
    ] = FieldFactory.concept_code_field(SpecimenSamplingProcedureCode)
    position: Optional[Union[str, Tuple[float, float, float]]] = None
