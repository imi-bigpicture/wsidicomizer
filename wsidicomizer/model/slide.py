from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from highdicom import (
    SpecimenDescription,
    SpecimenPreparationStep,
    SpecimenSampling,
    SpecimenStaining,
)
from pydicom import Dataset
from pydicom.sequence import Sequence as DicomSequence
from wsidicom.conceptcode import (
    ContainerComponentTypeCode,
    ContainerTypeCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
)

from wsidicomizer.model.sample import Sample


@dataclass
class Slide:
    slide_id: str = "Unknown"
    stainings: Sequence[SpecimenStainsCode] = field(default_factory=list)
    samples: Dict[Sample, Optional[Union[str, Tuple[float, float, float]]]] = field(
        default_factory=dict
    )

    def to_dataset(self) -> Dataset:
        dataset = Dataset()
        dataset.ContainerIdentifier = self.slide_id
        slide_container = ContainerTypeCode.from_code_meaning(
            "Microscope slide"
        ).to_ds()
        dataset.IssuerOfTheContainerIdentifierSequence = DicomSequence()
        dataset.ContainerTypeCodeSequence = DicomSequence([slide_container])
        slide_container_components = Dataset()
        slide_container_components.ContainerComponentMaterial = "GLASS"
        cover_slip = ContainerComponentTypeCode.from_code_meaning(
            "Microscope slide coverslip"
        ).to_ds()
        slide_container_components.ContainerComponentTypeCodeSequence = DicomSequence(
            [cover_slip]
        )
        dataset.ContainerComponentSequence = DicomSequence([slide_container_components])
        dataset.SpecimenDescriptionSequence = DicomSequence(
            [
                self.sample_to_description(block, location)
                for block, location in self.samples.items()
            ]
        )
        return dataset

    def sample_to_description(
        self, sample: Sample, location: Optional[Union[str, Tuple[float, float, float]]]
    ) -> SpecimenDescription:
        return SpecimenDescription(
            specimen_id=sample.sample_id,
            specimen_uid=sample.sample_uid,
            specimen_preparation_steps=self.sample_to_preparation_steps(sample),
            specimen_location=location,
            primary_anatomic_structures=[
                anatomical_site for anatomical_site in sample.anatomical_sites
            ],
        )

    def sample_to_preparation_steps(
        self, sample: Sample
    ) -> List[SpecimenPreparationStep]:
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        sample_preparation_steps.extend(sample.to_preparation_steps())
        slide_sample_step = SpecimenPreparationStep(
            self.slide_id,
            processing_procedure=SpecimenSampling(
                method=SpecimenSamplingProcedureCode.from_code_meaning(
                    "Block sectioning"
                ).code,
                parent_specimen_id=sample.sample_id,
                parent_specimen_type=sample.sample_type.code,
            ),
        )
        sample_preparation_steps.append(slide_sample_step)
        slide_staining_step = SpecimenPreparationStep(
            self.slide_id,
            processing_procedure=SpecimenStaining(
                [staining.code for staining in self.stainings]
            ),
        )
        sample_preparation_steps.append(slide_staining_step)
        return sample_preparation_steps
