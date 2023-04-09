from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union
from highdicom import (
    SpecimenDescription,
    SpecimenPreparationStep,
    SpecimenSampling,
    SpecimenStaining,
)

from pydicom import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.sr.coding import Code
from wsidicom.conceptcode import (
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
    AnatomicPathologySpecimenTypesCode,
    ConceptCode,
)
from pydicom.uid import UID, generate_uid


@dataclass
class Sample:
    sample_id: str
    sample_uid: UID = generate_uid()
    stainings: Optional[Sequence[SpecimenStainsCode]] = None
    embedding_medium: Optional[SpecimenEmbeddingMediaCode] = None
    fixative: Optional[SpecimenFixativesCode] = None
    specimen_id: Optional[str] = None
    specimen_type: Optional[AnatomicPathologySpecimenTypesCode] = None
    specimen_sampling_method: Optional[SpecimenSamplingProcedureCode] = None
    anatomical_sites: Optional[Sequence[Tuple[Code, Sequence[Code]]]] = None
    location: Optional[Union[str, Tuple[float, float, float]]] = None

    @classmethod
    def create_he_sample(cls, sample_id: str = "Unknown"):
        return cls(
            sample_id=sample_id,
            stainings=[
                SpecimenStainsCode.from_code_value("12710003"),
                SpecimenStainsCode.from_code_value("36879007"),
            ],
        )

    def to_dataset(self) -> Dataset:
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        if self.stainings is not None:
            sample_preparation_step = self.create_sample_preparation_step(
                self.sample_id, self.stainings, self.embedding_medium, self.fixative
            )
            sample_preparation_steps.append(sample_preparation_step)
        if self.specimen_id is not None:
            sample_sampling_step = self.create_sample_sampling_step(
                self.sample_id,
                self.specimen_id,
                self.specimen_sampling_method,
                self.specimen_type,
            )
            sample_preparation_steps.append(sample_sampling_step)

        specimen = SpecimenDescription(
            specimen_id=self.sample_id,
            specimen_uid=self.sample_uid,
            specimen_preparation_steps=sample_preparation_steps,
            specimen_location=self.location,
        )
        if self.anatomical_sites is not None:
            specimen.PrimaryAnatomicStructureSequence = (
                self.create_primary_anantomic_structure_sequence(self.anatomical_sites)
            )

        return specimen

    @staticmethod
    def create_sample_preparation_step(
        specimen_id: str,
        stainings: Sequence[SpecimenStainsCode],
        embedding_medium: Optional[SpecimenEmbeddingMediaCode],
        fixative: Optional[SpecimenFixativesCode],
    ) -> SpecimenPreparationStep:
        """Create SpecimenPreparationStep for a preparation step.

        Parameters
        ----------
        specimen_id: str
            ID of specimen that has been prepared.
        stainings: Sequence[str]
            Sequence of stainings used.
        embedding_medium: Optional[str] = None
            Embedding medium used.
        fixative: Optional[str] = None
            Fixative used.

        Returns
        ----------
        SpecimenPreparationStep
            SpecimenPreparationStep for a preparation step.
        """

        processing_procedure = SpecimenStaining(
            [staining.code for staining in stainings]
        )
        if fixative is None:
            fixative_code = None
        else:
            fixative_code = fixative.code
        if embedding_medium is None:
            embedding_medium_code = None
        else:
            embedding_medium_code = embedding_medium.code
        sample_preparation_step = SpecimenPreparationStep(
            specimen_id=specimen_id,
            processing_procedure=processing_procedure,
            embedding_medium=embedding_medium_code,
            fixative=fixative_code,
        )
        return sample_preparation_step

    @staticmethod
    def create_primary_anantomic_structure_sequence(
        anatomical_sites: Sequence[Tuple[Code, Sequence[Code]]]
    ) -> List[Dataset]:
        """Add anatomical site and anatomical site modifier codes to specimen.

        Parameters
        ----------
        specimen: Dataset
            Dataset containing a specimen description
        anatomical_sites: Sequence[Tuple[Code, Sequence[Code]]]
            List of original anatomical sites, each defined by a code and
            list of modifier codes (can be empty).

        Returns
        ----------
        Dataset
            Dataset containing a specimen description.
        """
        anatomical_site_datasets: List[Dataset] = []
        for (anatomical_site, modifiers) in anatomical_sites:
            anatomical_site_dataset = ConceptCode.from_code(anatomical_site).to_ds()

            if modifiers != []:
                modifier_datasets: List[Dataset] = []
                for modifier in modifiers:
                    modifier_dataset = Dataset()
                    modifier_dataset.CodeValue = modifier.value
                    modifier_dataset.CodingSchemeDesignator = modifier.scheme_designator
                    modifier_dataset.CodeMeaning = modifier.meaning
                    modifier_datasets.append(modifier_dataset)

                (
                    anatomical_site_dataset.PrimaryAnatomicStructureModifierSequence
                ) = DicomSequence(modifier_datasets)
            anatomical_site_datasets.append(anatomical_site_dataset)
        return anatomical_site_datasets

    @staticmethod
    def create_sample_sampling_step(
        sample_id: str,
        specimen_id: str,
        specimen_sampling_method: Optional[SpecimenSamplingProcedureCode],
        specimen_type: Optional[AnatomicPathologySpecimenTypesCode],
    ) -> SpecimenPreparationStep:
        """Create SpecimenPreparationStep for a sampling step.

        Parameters
        ----------
        sample_id: str
            ID of sample that has been created.
        specimen_id: str
            ID of specimen that was sampled.
        specimen_sampling_method: Optional[str]
            Method used to sample specimen.
        specimen_type: Optional[str]
            Type of specimen that was sampled

        Returns
        ----------
        SpecimenPreparationStep
            SpecimenPreparationStep for a sampling step.
        """
        if specimen_sampling_method is None:
            raise ValueError(
                "Specimen sampling method required if " "specimen id is defined"
            )
        if specimen_type is None:
            raise ValueError("Specimen type required if " "specimen id is defined")
        sample_sampling_step = SpecimenPreparationStep(
            specimen_id=sample_id,
            processing_procedure=SpecimenSampling(
                method=specimen_sampling_method.code,
                parent_specimen_id=specimen_id,
                parent_specimen_type=specimen_type.code,
            ),
        )
        return sample_sampling_step
