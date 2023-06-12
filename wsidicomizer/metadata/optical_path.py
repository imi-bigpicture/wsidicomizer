"""Optical path model."""
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from pydicom import Dataset
from pydicom import Sequence as DicomSequence
from wsidicom.conceptcode import IlluminationCode, IlluminationColorCode
from wsidicom.instance import ImageType

from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomByteAttribute,
    DicomCodeAttribute,
    DicomNumberAttribute,
    DicomStringAttribute,
)
from wsidicomizer.metadata.fields import FieldFactory
from wsidicomizer.metadata.model_base import ModelBase


@dataclass
class OpticalPath(ModelBase):
    """
    Optical path metadata.

    Corresponds to the `Required`, `Required, Empty if Unknown`, and selected
    `Optional` attributes for an Optical Path Sequence item in the Optical Path Module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html
    """

    identifier: Optional[str] = None
    description: Optional[str] = None
    illumination_type: Optional[IlluminationCode] = FieldFactory.concept_code_field(
        IlluminationCode
    )
    illumination: Optional[
        Union[float, IlluminationColorCode]
    ] = FieldFactory.float_or_concent_code_field(IlluminationColorCode)
    icc_profile: Optional[bytes] = None
    objective_lens_power: Optional[float] = None
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        if "OpticalPathSequence" not in dataset:
            dataset.OpticalPathSequence = DicomSequence()
        optical_path = Dataset()
        dicom_attributes: List[DicomAttribute] = [
            DicomStringAttribute(
                "OpticalPathIdentifier",
                True,
                self.identifier,
                lambda: self._generate_unique_identifier(dataset.OpticalPathSequence),
            ),
            DicomCodeAttribute(
                "IlluminationTypeCodeSequence",
                True,
                self.illumination_type.code
                if self.illumination_type is not None
                else None,
                IlluminationCode("Brightfield illumination").code,
            ),
            DicomStringAttribute("OpticalPathDescription", False, self.description),
            DicomByteAttribute(
                "ICCProfile",
                True,
                self.icc_profile,
            ),
            DicomNumberAttribute(
                "ObjectiveLensPower", False, self.objective_lens_power
            ),
        ]
        if isinstance(self.illumination, float):
            dicom_attributes.append(
                DicomNumberAttribute("IlluminationWaveLength", True, self.illumination)
            )
        else:
            dicom_attributes.append(
                DicomCodeAttribute(
                    "IlluminationColorCodeSequence",
                    True,
                    self.illumination.code if self.illumination is not None else None,
                    IlluminationColorCode("Full Spectrum").code,
                )
            )
        self._insert_dicom_attributes_into_dataset(optical_path, dicom_attributes)
        dataset.OpticalPathSequence.append(optical_path)

    @staticmethod
    def _generate_unique_identifier(optical_paths: DicomSequence) -> str:
        identifiers = [
            optical_path.OpticalPathIdentifier for optical_path in optical_paths
        ]
        identifier = 0
        while identifier in identifiers:
            identifier += 1
        return str(identifier)
