from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from highdicom import (
    SpecimenCollection,
    SpecimenDescription,
    SpecimenPreparationStep,
    SpecimenProcessing,
    SpecimenSampling,
    SpecimenStaining,
)
from pydicom import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.sr.coding import Code
from pydicom.uid import UID, generate_uid
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    ContainerComponentTypeCode,
    ContainerTypeCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationProcedureCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
)


@dataclass
class Specimen:
    specimen_id: str
    specimen_type: AnatomicPathologySpecimenTypesCode
    specimen_extraction_method: SpecimenCollectionProcedureCode
    specimen_fixation_type: SpecimenFixativesCode
    specimen_anatomical_sites: Sequence[Code]

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        specimen_sampling_step = SpecimenPreparationStep(
            self.specimen_id,
            processing_procedure=SpecimenCollection(
                procedure=self.specimen_extraction_method.code,
            ),
        )
        specimen_preparation_step = SpecimenPreparationStep(
            specimen_id=self.specimen_id,
            processing_procedure=SpecimenProcessing(
                SpecimenPreparationProcedureCode.from_code_meaning(
                    "Specimen processing"
                ).code
            ),
            fixative=self.specimen_fixation_type.code,
        )
        return [specimen_sampling_step, specimen_preparation_step]


@dataclass
class Sample(metaclass=ABCMeta):
    sample_id: str
    sample_type: AnatomicPathologySpecimenTypesCode
    sample_uid: UID

    @abstractmethod
    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        raise NotImplementedError()

    @property
    @abstractmethod
    def anatomical_sites(self) -> Sequence[Code]:
        raise NotImplementedError()


@dataclass
class Block(Sample):
    sample_id: str
    block_preparation: SpecimenEmbeddingMediaCode
    specimens: Dict[Specimen, Optional[SpecimenSamplingProcedureCode]]
    sample_uid: UID = generate_uid()
    sample_type: AnatomicPathologySpecimenTypesCode = (
        AnatomicPathologySpecimenTypesCode.from_code_meaning("Gross specimen")
    )

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        for specimen, sampling_method in self.specimens.items():
            if sampling_method is None:
                sampling_method = SpecimenSamplingProcedureCode.from_code_meaning(
                    "Dissection"
                )
            sample_preparation_steps.extend(specimen.to_preparation_steps())
            block_sampling_step = SpecimenPreparationStep(
                self.sample_id,
                processing_procedure=SpecimenSampling(
                    method=sampling_method.code,
                    parent_specimen_id=specimen.specimen_id,
                    parent_specimen_type=specimen.specimen_type.code,
                ),
            )
            sample_preparation_steps.append(block_sampling_step)
        block_preparation_step = SpecimenPreparationStep(
            specimen_id=self.sample_id,
            processing_procedure=SpecimenProcessing(
                SpecimenPreparationProcedureCode.from_code_meaning(
                    "Specimen processing"
                ).code
            ),
            embedding_medium=self.block_preparation.code,
        )
        sample_preparation_steps.append(block_preparation_step)
        return sample_preparation_steps

    @property
    def anatomical_sites(self) -> Sequence[Code]:
        return [
            anatomical_site
            for specimen in self.specimens
            for anatomical_site in specimen.specimen_anatomical_sites
        ]


@dataclass
class SimpleSample(Sample):
    sample_id: str
    sample_type: AnatomicPathologySpecimenTypesCode
    sample_uid: UID = generate_uid()
    embedding_medium: Optional[SpecimenEmbeddingMediaCode] = None
    fixative: Optional[SpecimenFixativesCode] = None
    specimen_id: Optional[str] = None
    specimen_type: Optional[AnatomicPathologySpecimenTypesCode] = None
    specimen_sampling_method: Optional[SpecimenSamplingProcedureCode] = None
    anatomical_sites: Optional[Sequence[Code]] = None

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        sample_preparation_steps: List[SpecimenPreparationStep] = []

        if (
            self.specimen_id is not None
            and self.specimen_sampling_method is not None
            and self.specimen_type is not None
        ):
            sample_sampling_step = SpecimenPreparationStep(
                specimen_id=self.sample_id,
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
                specimen_id=self.sample_id,
                processing_procedure=SpecimenProcessing(
                    SpecimenPreparationProcedureCode.from_code_meaning(
                        "Specimen processing"
                    ).code
                ),
                embedding_medium=embedding_medium,
                fixative=fixative,
            )
            sample_preparation_steps.append(preparation_step)

        return sample_preparation_steps
