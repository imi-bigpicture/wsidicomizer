import datetime
from typing import List, Literal, Optional, Union

from pydicom import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.sr.coding import Code
from wsidicom.instance import ImageType

from wsidicomizer.metadata.base import (
    DicomCodeAttribute,
    DicomDateTimeAttribute,
    DicomModelBase,
    DicomStringAttribute,
)


class PatientDeIdentification(DicomModelBase):
    def __init__(
        self, identity_removed: bool, methods: Optional[List[Union[str, Code]]] = None
    ):
        self._identity_removed = identity_removed
        self._methods = methods

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dataset.PatientIdentityRemoved = self._bool_to_literal(self._identity_removed)
        if self._methods is not None:
            for method in self._methods:
                if isinstance(method, str):
                    if "DeidentificationMethod" not in dataset:
                        dataset.DeidentificationMethod = []
                    dataset.DeidentificationMethod.append(method)
                else:
                    if "DeidentificationMethodCodeSequence" not in dataset:
                        dataset.DeidentificationMethodCodeSequence = DicomSequence()
                    dataset.DeidentificationMethodCodeSequence.append(
                        self._code_to_code_sequence_item(method)
                    )
        elif self._identity_removed:
            raise ValueError("")


class Patient(DicomModelBase):
    """
    Patient metadata.

    Corresponds to the `Required` and `Required, Empty if Unknown` attributes in the
    Patient Module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html
    """

    def __init__(
        self,
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        birth_date: Optional[datetime.date] = None,
        sex: Optional[Literal["F", "M", "O"]] = None,
        species_description: Optional[Union[str, Code]] = None,
        de_identification: Optional[PatientDeIdentification] = None,
    ):
        self._name = DicomStringAttribute("PatientName", False, name)
        self._identifier = DicomStringAttribute("PatientID", False, identifier)
        self._birth_date = DicomDateTimeAttribute("PatientBirthDate", False, birth_date)
        self._sex = DicomStringAttribute("PatientSex", False, sex)
        if isinstance(species_description, str):
            self._species_description = DicomStringAttribute(
                "PatientSpeciesDescription", False, species_description
            )
        elif isinstance(species_description, Code):
            self._species_description = DicomCodeAttribute(
                "PatientSpeciesCodeSequence",
                False,
                species_description,
                formater=lambda x: DicomSequence([self._code_to_code_sequence_item(x)]),
            )
        else:
            self._species_description = None
        self._de_identification = de_identification
        self._dicom_attributes = [
            self._name,
            self._identifier,
            self._birth_date,
            self._sex,
            self._species_description,
        ]

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        self._insert_dicom_attributes_into_dataset(dataset)
        if self._de_identification is not None:
            self._de_identification.insert_into_dataset(dataset, image_type)
