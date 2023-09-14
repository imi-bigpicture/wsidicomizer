"""Slide model."""
from dataclasses import dataclass
from typing import Sequence, List, Optional, Sequence
from pydicom import Dataset
from pydicom.sequence import Sequence as DicomSequence
from wsidicom.instance import ImageType
from wsidicomizer.metadata.defaults import defaults

from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomCodeAttribute,
    DicomSequenceAttribute,
    DicomStringAttribute,
)
from wsidicomizer.metadata.base_model import BaseModel

from wsidicomizer.metadata.sample import SlideSample, Staining


@dataclass
class Slide(BaseModel):
    """
    Metadata for a slide.

    A slide has a an identifier and contains one or more samples. The position of the
    samples can be specified using a SampleLocation. All the samples on the slide has
    been stained with the sample list of stainings.
    """

    identifier: Optional[str] = None
    stains: Optional[Sequence[Staining]] = None
    samples: Optional[Sequence[SlideSample]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomStringAttribute(
                "ContainerIdentifier", True, self.identifier, defaults.string
            ),
            DicomCodeAttribute(
                "ContainerTypeCodeSequence",
                True,
                defaults.slide_container_type,
            ),
            DicomSequenceAttribute("IssuerOfTheContainerIdentifierSequence", True, []),
            DicomSequenceAttribute(
                "ContainerComponentSequence",
                False,
                [
                    DicomCodeAttribute(
                        "ContainerComponentTypeCodeSequence",
                        True,
                        defaults.slide_component_type,
                    ),
                    DicomStringAttribute(
                        "ContainerComponentMaterial", False, defaults.slide_material
                    ),
                ],
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)
        if self.samples is not None:
            dataset.SpecimenDescriptionSequence = DicomSequence(
                [
                    slide_sample.to_description(self.stains)
                    for slide_sample in self.samples
                ]
            )
        else:
            dataset.SpecimenDescriptionSequence = DicomSequence()

    @classmethod
    def from_dataset(cls, dataset: Dataset):
        identifier = dataset.ContainerIdentifier
        samples, stains = SlideSample.from_dataset(dataset)

        return cls(identifier=identifier, stains=stains, samples=samples)
