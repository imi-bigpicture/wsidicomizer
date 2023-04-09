from dataclasses import dataclass, field
from typing import List

from pydicom import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.sr.coding import Code
from wsidicomizer.model.sample import Sample
from wsidicomizer.model.util import code_to_dataset


SLIDE_CONTAINER = code_to_dataset(Code("433466003", "SCT", "Microscope slide"))

COVERSLIP_COMPONENT = Dataset()
COVERSLIP_COMPONENT.ContainerComponentMaterial = "GLASS"
COVERSLIP_COMPONENT.ContainerComponentTypeCodeSequence = DicomSequence(
    [code_to_dataset(Code("433472003", "SCT", "Microscope slide coverslip"))]
)


@dataclass
class Slide:
    slide_id: str = "Unknown"
    samples: List[Sample] = field(default_factory=lambda: [Sample.create_he_sample()])

    def to_dataset(self) -> Dataset:
        dataset = Dataset()
        dataset.ContainerIdentifier = self.slide_id
        dataset.IssuerOfTheContainerIdentifierSequence = DicomSequence()
        dataset.ContainerTypeCodeSequence = DicomSequence([SLIDE_CONTAINER])
        dataset.ContainerComponentSequence = DicomSequence([COVERSLIP_COMPONENT])
        dataset.SpecimenDescriptionSequence = DicomSequence(
            [sample.to_dataset() for sample in self.samples]
        )
        return dataset
