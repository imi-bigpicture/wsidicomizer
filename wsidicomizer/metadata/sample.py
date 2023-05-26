from abc import ABCMeta, abstractmethod
from typing import Dict, List, Optional, Sequence

from highdicom import (
    SpecimenCollection,
    SpecimenPreparationStep,
    SpecimenProcessing,
    SpecimenSampling,
)
from pydicom.sr.coding import Code
from pydicom.uid import UID, generate_uid
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationProcedureCode,
    SpecimenSamplingProcedureCode,
)


class Sample(metaclass=ABCMeta):
    def __init__(
        self, identifier: str, type: AnatomicPathologySpecimenTypesCode, uid: UID
    ):
        self._identifier = identifier
        self._type = type
        self._uid = uid

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def type(self) -> AnatomicPathologySpecimenTypesCode:
        return self._type

    @property
    def uid(self) -> UID:
        return self._uid

    @abstractmethod
    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        raise NotImplementedError()

    @property
    @abstractmethod
    def anatomical_sites(self) -> Sequence[Code]:
        """Should return all the anatomical sites present in the sample hierarchy."""
        raise NotImplementedError()


class Specimen(Sample):
    """A specimen that has been extracted from a patient."""

    def __init__(
        self,
        identifier: str,
        type: AnatomicPathologySpecimenTypesCode,
        extraction_method: SpecimenCollectionProcedureCode,
        fixation_type: SpecimenFixativesCode,
        anatomical_sites: Sequence[Code],
        uid: UID = generate_uid(),
    ):
        super().__init__(identifier, type, uid)
        self._extraction_method = extraction_method
        self._fixation_type = fixation_type
        self._anatomical_sites = anatomical_sites

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        specimen_sampling_step = SpecimenPreparationStep(
            self.identifier,
            processing_procedure=SpecimenCollection(
                procedure=self._extraction_method.code,
            ),
        )
        specimen_preparation_step = SpecimenPreparationStep(
            specimen_id=self.identifier,
            processing_procedure=SpecimenProcessing(
                SpecimenPreparationProcedureCode.from_code_meaning(
                    "Specimen processing"
                ).code
            ),
            fixative=self._fixation_type.code,
        )
        return [specimen_sampling_step, specimen_preparation_step]

    @property
    def anatomical_sites(self) -> Sequence[Code]:
        return self._anatomical_sites


class Block(Sample):
    """A block that has been sampled from one or more specimens."""

    def __init__(
        self,
        identifier: str,
        type: AnatomicPathologySpecimenTypesCode,
        embedding_medium: SpecimenEmbeddingMediaCode,
        specimens: Dict[Specimen, Optional[SpecimenSamplingProcedureCode]],
        uid: UID = generate_uid(),
    ):
        super().__init__(identifier, type, uid)
        self._specimens = specimens
        self._embedding_medium = embedding_medium

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        for specimen, sampling_method in self._specimens.items():
            if sampling_method is None:
                sampling_method = SpecimenSamplingProcedureCode.from_code_meaning(
                    "Dissection"
                )
            sample_preparation_steps.extend(specimen.to_preparation_steps())
            block_sampling_step = SpecimenPreparationStep(
                self._identifier,
                processing_procedure=SpecimenSampling(
                    method=sampling_method.code,
                    parent_specimen_id=specimen.identifier,
                    parent_specimen_type=specimen.type.code,
                ),
            )
            sample_preparation_steps.append(block_sampling_step)
        block_preparation_step = SpecimenPreparationStep(
            specimen_id=self._identifier,
            processing_procedure=SpecimenProcessing(
                SpecimenPreparationProcedureCode.from_code_meaning(
                    "Specimen processing"
                ).code
            ),
            embedding_medium=self._embedding_medium.code,
        )
        sample_preparation_steps.append(block_preparation_step)
        return sample_preparation_steps

    @property
    def anatomical_sites(self) -> Sequence[Code]:
        return [
            anatomical_site
            for specimen in self._specimens
            for anatomical_site in specimen.anatomical_sites
        ]


class SimpleSample(Sample):
    """Simple sample without sampling hierarchy."""

    def __init__(
        self,
        identifier: str,
        type: AnatomicPathologySpecimenTypesCode,
        embedding_medium: Optional[SpecimenEmbeddingMediaCode] = None,
        fixative: Optional[SpecimenFixativesCode] = None,
        specimen_id: Optional[str] = None,
        specimen_type: Optional[AnatomicPathologySpecimenTypesCode] = None,
        specimen_sampling_method: Optional[SpecimenSamplingProcedureCode] = None,
        anatomical_sites: Optional[Sequence[Code]] = None,
        uid: UID = generate_uid(),
    ):
        super().__init__(identifier, type, uid)
        self._embedding_medium = embedding_medium
        self._fixative = fixative
        self._specimen_id = specimen_id
        self._specimen_type = specimen_type
        self._specimen_sampling_method = specimen_sampling_method
        if anatomical_sites is None:
            anatomical_sites = []
        self._anatomical_sites = anatomical_sites

    def to_preparation_steps(self) -> List[SpecimenPreparationStep]:
        sample_preparation_steps: List[SpecimenPreparationStep] = []

        if (
            self._specimen_id is not None
            and self._specimen_sampling_method is not None
            and self._specimen_type is not None
        ):
            sample_sampling_step = SpecimenPreparationStep(
                specimen_id=self._identifier,
                processing_procedure=SpecimenSampling(
                    method=self._specimen_sampling_method.code,
                    parent_specimen_id=self._specimen_id,
                    parent_specimen_type=self._specimen_type.code,
                ),
            )
            sample_preparation_steps.append(sample_sampling_step)
        if self._embedding_medium is not None:
            embedding_medium = self._embedding_medium.code
        else:
            embedding_medium = None
        if self._fixative is not None:
            fixative = self._fixative.code
        else:
            fixative = None
        if embedding_medium is not None or fixative is not None:
            preparation_step = SpecimenPreparationStep(
                specimen_id=self._identifier,
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

    @property
    def anatomical_sites(self) -> Sequence[Code]:
        return self._anatomical_sites
