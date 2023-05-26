from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

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
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base import DicomModelBase
from wsidicomizer.metadata.sample import Sample


@dataclass
class SampleLocation:
    description: Optional[str] = None
    position: Optional[Tuple[float, float, float]] = None


class Slide(DicomModelBase):
    """
    Metadata for a slide.

    A slide has a an identifier and contains one or more samples. The position of the
    samples can be specified using a SampleLocation. All the samples on the slide has
    been stained with the samle list of stainings.
    """

    def __init__(
        self,
        identifier: str = "Unknown",
        stainings: Sequence[SpecimenStainsCode] = field(default_factory=list),
        samples: Dict[Sample, SampleLocation] = field(default_factory=dict),
    ):
        self._identifier = identifier
        self._stainings = stainings
        self._samples = samples

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dataset.ContainerIdentifier = self._identifier
        slide_container = ContainerTypeCode.from_code_meaning(
            "Microscope slide"
        ).to_ds()
        dataset.IssuerOfTheContainerIdentifierSequence = DicomSequence()
        dataset.ContainerTypeCodeSequence = DicomSequence([slide_container])
        slide_container_components = Dataset()
        slide_container_components.ContainerComponentMaterial = "GLASS"
        ContainerComponentTypeCode.from_code_meaning(
            "Microscope slide coverslip"
        ).insert_into_ds(slide_container_components)
        dataset.ContainerComponentSequence = DicomSequence([slide_container_components])
        dataset.SpecimenDescriptionSequence = DicomSequence(
            [
                self._sample_to_description(block, location)
                for block, location in self._samples.items()
            ]
        )

    def _sample_to_description(
        self, sample: Sample, location: SampleLocation
    ) -> SpecimenDescription:
        """Create a SpecimenDescription item for a sample."""
        if location.position is not None:
            specimen_location = location.position
        elif location.description is not None:
            specimen_location = location.description
        else:
            specimen_location = None
        return SpecimenDescription(
            specimen_id=sample.identifier,
            specimen_uid=sample.uid,
            specimen_preparation_steps=self._sample_to_preparation_steps(sample),
            specimen_location=specimen_location,
            primary_anatomic_structures=[
                anatomical_site for anatomical_site in sample.anatomical_sites
            ],
        )

    def _sample_to_preparation_steps(
        self, sample: Sample
    ) -> List[SpecimenPreparationStep]:
        """Create SpecimenPreparationStep items for a sample."""
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        sample_preparation_steps.extend(sample.to_preparation_steps())
        slide_sample_step = SpecimenPreparationStep(
            self._identifier,
            processing_procedure=SpecimenSampling(
                method=SpecimenSamplingProcedureCode.from_code_meaning(
                    "Block sectioning"
                ).code,
                parent_specimen_id=sample.identifier,
                parent_specimen_type=sample.type.code,
            ),
        )
        sample_preparation_steps.append(slide_sample_step)
        slide_staining_step = SpecimenPreparationStep(
            self._identifier,
            processing_procedure=SpecimenStaining(
                [staining.code for staining in self._stainings]
            ),
        )
        sample_preparation_steps.append(slide_staining_step)
        return sample_preparation_steps
