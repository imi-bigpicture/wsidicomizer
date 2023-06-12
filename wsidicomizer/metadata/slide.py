"""Slide model."""
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple, Union
from dataclasses_json import dataclass_json

from highdicom import (
    SpecimenDescription,
    SpecimenPreparationStep,
    SpecimenSampling,
    SpecimenStaining,
)
from pydicom import Dataset
from pydicom.uid import generate_uid
from pydicom.sequence import Sequence as DicomSequence
from wsidicom.conceptcode import (
    ContainerComponentTypeCode,
    ContainerTypeCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
)
from wsidicom.instance import ImageType

from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomCodeAttribute,
    DicomSequenceAttribute,
    DicomStringAttribute,
)
from wsidicomizer.metadata.fields import FieldFactory
from wsidicomizer.metadata.model_base import ModelBase
from wsidicomizer.metadata.sample import SlideSample



@dataclass
class Slide(ModelBase):
    """
    Metadata for a slide.

    A slide has a an identifier and contains one or more samples. The position of the
    samples can be specified using a SampleLocation. All the samples on the slide has
    been stained with the samle list of stainings.
    """

    identifier: Optional[str] = None
    stains: Optional[
        Iterable[SpecimenStainsCode]
    ] = FieldFactory.list_concept_code_field(SpecimenStainsCode)
    samples: Iterable[SlideSample] = field(default_factory=list)
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomStringAttribute(
                "ContainerIdentifier", True, self.identifier, "Unknown"
            ),
            DicomCodeAttribute(
                "ContainerTypeCodeSequence",
                True,
                ContainerTypeCode("Microscope slide").code,
            ),
            DicomSequenceAttribute("IssuerOfTheContainerIdentifierSequence", True, []),
            DicomSequenceAttribute(
                "ContainerComponentSequence",
                False,
                [
                    DicomCodeAttribute(
                        "ContainerComponentTypeCodeSequence",
                        False,
                        ContainerComponentTypeCode("Microscope slide cover slip").code,
                    ),
                    DicomStringAttribute("ContainerComponentMaterial", False, "GLASS"),
                ],
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)
        if self.samples is not None:
            dataset.SpecimenDescriptionSequence = DicomSequence(
                [
                    self._sample_to_description(
                        dataset.ContainerIdentifier,
                        slide_sample.sample,
                        slide_sample.sampling_method,
                        slide_sample.position,
                    )
                    for slide_sample in self.samples
                ]
            )

    def _sample_to_description(
        self,
        slide_identifier: str,
        sample: Sample,
        sampling_method: Optional[SpecimenSamplingProcedureCode],
        position: Optional[Union[str, Tuple[float, float, float]]],
    ) -> SpecimenDescription:
        """Create a SpecimenDescription item for a sample."""
        if sampling_method is None:
            sampling_method = SpecimenSamplingProcedureCode("Block sectioning")
        sample_uid = generate_uid() if sample.uid is None else sample.uid
        return SpecimenDescription(
            specimen_id=sample.identifier,
            specimen_uid=sample_uid,
            specimen_preparation_steps=self._sample_to_preparation_steps(
                slide_identifier, sample, sampling_method
            ),
            specimen_location=position,
            primary_anatomic_structures=[
                anatomical_site for anatomical_site in sample.anatomical_sites
            ],
        )

    def _sample_to_preparation_steps(
        self,
        slide_identifier: str,
        sample: Sample,
        sampling_method: SpecimenSamplingProcedureCode,
    ) -> List[SpecimenPreparationStep]:
        """Create SpecimenPreparationStep items for a sample."""
        sample_preparation_steps: List[SpecimenPreparationStep] = []
        sample_preparation_steps.extend(sample.to_preparation_steps())
        slide_sample_step = SpecimenPreparationStep(
            slide_identifier,
            processing_procedure=sample.to_sampling_step(sampling_method),
        )
        sample_preparation_steps.append(slide_sample_step)
        if self.stains is not None:
            slide_staining_step = SpecimenPreparationStep(
                slide_identifier,
                processing_procedure=SpecimenStaining(
                    [stain.code for stain in self.stains]
                ),
            )
            sample_preparation_steps.append(slide_staining_step)
        return sample_preparation_steps
