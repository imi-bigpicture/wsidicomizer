from collections import defaultdict
from typing import Any, Dict, Type
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    BooleanDicomField,
    CodeDicomField,
    DateDicomField,
    FlatteningNestedField,
    ListDicomField,
    PatientNameDicomField,
    SingleCodeDicomField,
    NoneDicomField,
)
from marshmallow import fields, pre_dump, post_load
from pydicom.sr.coding import Code
from wsidicomizer.metadata.patient import Patient, PatientDeIdentification, PatientSex


class PatientDeIdentificationDicomSchema(DicomSchema[PatientDeIdentification]):
    identity_removed = BooleanDicomField(data_key="PatientIdentityRemoved")
    method_strings = ListDicomField(fields.String(), data_key="DeidentificationMethod")
    method_codes = fields.List(
        CodeDicomField(Code), data_key="DeidentificationMethodCodeSequence"
    )

    @property
    def load_type(self) -> Type[PatientDeIdentification]:
        return PatientDeIdentification

    @pre_dump
    def pre_dump(self, de_identification: PatientDeIdentification, **kwargs):
        fields = {"identity_removed": de_identification.identity_removed}
        if de_identification.methods is not None:
            de_identification_fields = defaultdict(list)
            for method in de_identification.methods:
                if isinstance(method, str):
                    de_identification_fields["method_strings"].append(method)
                else:
                    de_identification_fields["method_codes"].append(method)
            fields.update(de_identification_fields)
        return fields

    @post_load
    def post_load(self, data: Dict[str, Any], **kwargs):
        method_strings = data.pop("method_strings", [])
        method_codes = data.pop("method_codes", [])
        methods = method_strings + method_codes
        if len(methods) > 0:
            data["methods"] = methods
        return super().post_load(data, **kwargs)


class PatientDicomSchema(DicomSchema[Patient]):
    """
    Type 1:
    - method_strings (if identity_removed)
    - method_codes (if identity_removed)
    Type 2:
    - name
    - idenentifier
    - birth_date
    - sex
    Type 3:
    - identity_removed
    """

    name = NoneDicomField(PatientNameDicomField(), data_key="PatientName")
    identifier = NoneDicomField(fields.String(), data_key="PatientID")
    birth_date = NoneDicomField(DateDicomField(), data_key="PatientBirthDate")
    sex = NoneDicomField(fields.Enum(PatientSex), data_key="PatientSex")
    species_description_string = fields.String(
        data_key="PatientSpeciesDescription", allow_none=True
    )
    species_description_code = SingleCodeDicomField(
        Code, data_key="PatientSpeciesCodeSequence", allow_none=True
    )
    de_identification = FlatteningNestedField(PatientDeIdentificationDicomSchema())

    @property
    def load_type(self) -> Type[Patient]:
        return Patient

    @pre_dump
    def pre_dump(self, patient: Patient, **kwargs):
        fields = {
            "name": patient.name,
            "identifier": patient.identifier,
            "birth_date": patient.birth_date,
            "sex": patient.sex,
            "de_identification": patient.de_identification,
        }

        if isinstance(patient.species_description, str):
            fields["species_description_string"] = patient.species_description
        elif isinstance(patient.species_description, Code):
            fields["species_description_code"] = patient.species_description
        return fields

    @post_load
    def post_load(self, data: Dict[str, Any], **kwargs):
        species_description_string = data.pop("species_description_string", None)
        species_description_code = data.pop("species_description_code", None)
        if species_description_code is not None:
            data["species_description"] = species_description_code
        elif species_description_string is not None:
            data["species_description"] = species_description_string
        return super().post_load(data, **kwargs)
