#    Copyright 2023 SECTRA AB
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Patient model."""
import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Union

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
from wsidicomizer.metadata.base_model import BaseModel


class PatientSex(Enum):
    F = "female"
    M = "male"
    O = "other"


@dataclass
class PatientDeIdentification(BaseModel):
    identity_removed: bool
    methods: Optional[Sequence[Union[str, Code]]] = None

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

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "PatientDeIdentification":
        identity_removed = dataset.PatientIdentityRemoved
        methods: List[Union[str, Code]] = [
            method for method in dataset.DeidentificationMethod
        ]
        methods.extend(
            [
                Code(
                    method.CodeValue,
                    method.CodingSchemeDesignator,
                    method.CodeMeaning,
                    getattr(method, "CodeSchemeVersion", None),
                )
                for method in dataset.DeidentificationMethodCodeSequence
            ]
        )
        if identity_removed and len(methods) == 0:
            # TODO raise or warning?
            pass
        return cls(identity_removed, methods)


@dataclass
class Patient(BaseModel):
    """
    Patient metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    Patient Module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html
    """

    name: Optional[str] = None
    identifier: Optional[str] = None
    birth_date: Optional[datetime.date] = None
    sex: Optional[PatientSex] = None
    species_description: Optional[Union[str, Code]] = None
    de_identification: Optional[PatientDeIdentification] = None

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

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "Patient":
        if hasattr(dataset, "PatientSpeciesDescription"):
            species = dataset.PatientSpeciesDescription
        elif hasattr(dataset, "PatientSpeciesCodeSequence"):
            species = Code(
                dataset.PatientSpeciesCodeSequence[0].CodeValue,
                dataset.PatientSpeciesCodeSequence[0].CodingSchemeDesignator,
                dataset.PatientSpeciesCodeSequence[0].CodeMeaning,
                getattr(
                    dataset.PatientSpeciesCodeSequence[0], "CodeSchemeVersion", None
                ),
            )
        else:
            species = None
        return cls(
            dataset.PatientName,
            dataset.PatientID,
            dataset.PatientBirthDate,
            dataset.PatientSex,
            species,
            PatientDeIdentification.from_dataset(dataset),
        )
