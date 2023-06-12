"""Patient model."""
import datetime
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Union

from pydicom import Dataset
from pydicom.sr.coding import Code
from wsidicom.instance import ImageType

from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomBoolAttribute,
    DicomCodeAttribute,
    DicomDateTimeAttribute,
    DicomListStringAttribute,
    DicomStringAttribute,
)
from wsidicomizer.metadata.fields import FieldFactory
from wsidicomizer.metadata.model_base import ModelBase


@dataclass
class PatientDeIdentification(ModelBase):
    identity_removed: bool
    methods: Optional[
        List[Union[str, Code]]
    ] = None  # FieldFactory.list_string_or_code_field()
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomBoolAttribute("PatientIdentityRemoved", True, self.identity_removed)
        ]
        if self.methods is not None:
            for method in self.methods:
                if isinstance(method, str):
                    method_attribute = DicomListStringAttribute(
                        "DeidentificationMethod", False, method
                    )
                else:
                    method_attribute = DicomCodeAttribute(
                        "DeidentificationMethodCodeSequence", False, method
                    )
                dicom_attributes.append(method_attribute)

        elif self.identity_removed:
            raise ValueError(
                "If patient identity is removed at least on de-identification method "
                "must be given."
            )
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)


@dataclass
class Patient(ModelBase):
    """
    Patient metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    Patient Module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html
    """

    name: Optional[str] = None
    identifier: Optional[str] = None
    birth_date: Optional[datetime.date] = FieldFactory.date_field()
    sex: Optional[Literal["F", "M", "O"]] = None
    species_description: Optional[
        Union[str, Code]
    ] = FieldFactory.string_or_code_field()
    de_identification: Optional[PatientDeIdentification] = None
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes: List[DicomAttribute] = [
            DicomStringAttribute("PatientName", True, self.name),
            DicomStringAttribute("PatientID", True, self.identifier),
            DicomDateTimeAttribute("PatientBirthDate", True, self.birth_date),
            DicomStringAttribute("PatientSex", True, self.sex),
        ]
        if isinstance(self.species_description, str):
            dicom_attributes.append(
                DicomStringAttribute(
                    "PatientSpeciesDescription", False, self.species_description
                )
            )
        elif isinstance(self.species_description, Code):
            dicom_attributes.append(
                DicomCodeAttribute(
                    "PatientSpeciesCodeSequence",
                    False,
                    self.species_description,
                )
            )
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)
        if self.de_identification is not None:
            self.de_identification.insert_into_dataset(dataset, image_type)
