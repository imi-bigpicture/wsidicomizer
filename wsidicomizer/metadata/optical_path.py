from typing import Optional, Union

from pydicom import Dataset
from pydicom import Sequence as DicomSequence
from wsidicom.conceptcode import IlluminationCode, IlluminationColorCode
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base import (
    DicomByteAttribute,
    DicomCodeAttribute,
    DicomModelBase,
    DicomNumberAttribute,
    DicomStringAttribute,
)


class OpticalPath(DicomModelBase):
    """
    Optical path metadata.

    Corresponds to the `Required`, `Required, Empty if Unknown`, and selected
    `Optional` attributes for an Optical Path Sequence item in the Optical Path Module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html
    """

    def __init__(
        self,
        identifier: str,
        illumination_type: Optional[IlluminationCode] = None,
        description: Optional[str] = None,
        illumination: Optional[Union[float, IlluminationColorCode]] = None,
        icc_profile: Optional[bytes] = None,
        objective_lens_power: Optional[float] = None,
    ):
        self._identifier = DicomStringAttribute(
            "OpticalPathIdentifier", True, identifier
        )
        self._illumination_type = DicomCodeAttribute(
            "IlluminationTypeCodeSequence",
            True,
            illumination_type.code if illumination_type is not None else None,
            lambda: IlluminationCode.from_code_meaning("Brightfield illumination").code,
            self._code_to_code_sequence_item,
        )
        self._description = DicomStringAttribute(
            "OpticalPathDescription", False, description
        )
        if isinstance(illumination, float):
            self._illumination = DicomNumberAttribute(
                "IlluminationWaveLength", True, illumination
            )
        else:
            self._illumination = DicomCodeAttribute(
                "IlluminationColorCodeSequence",
                True,
                illumination.code if illumination is not None else None,
                lambda: IlluminationColorCode.from_code_meaning("Full Spectrum").code,
                self._code_to_code_sequence_item,
            )
        self._icc_profile = DicomByteAttribute(
            "ICCProfile",
            True,
            icc_profile,
        )
        self._objective_lens_power = DicomNumberAttribute(
            "ObjectiveLensPower", False, objective_lens_power
        )
        self._dicom_attributes = [
            self._identifier,
            self._illumination_type,
            self._description,
            self._illumination,
            self._icc_profile,
            self._objective_lens_power,
        ]

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        if "OpticalPathSequence" not in dataset:
            dataset.OpticalPathSequence = DicomSequence()
        optical_path = Dataset()
        self._insert_dicom_attributes_into_dataset(optical_path)
        dataset.OpticalPathSequence.append(optical_path)
