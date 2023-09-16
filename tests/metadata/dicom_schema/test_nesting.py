from typing import Type

import marshmallow
from marshmallow import pre_load
from pydicom import Dataset
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from wsidicomizer.metadata.dicom_schema.dicom_fields import FlatteningNestedField


class PropertySchema(DicomSchema):
    value = marshmallow.fields.String(data_key="PatientID")

    @property
    def load_type(self) -> Type[dict]:
        return dict

    @pre_load
    def pre_load(self, dataset: Dataset, many: bool, **kwargs):
        print("property pre load", dataset)
        return super().pre_load(dataset, many, **kwargs)


class ChildSchema(DicomSchema):
    nested = FlatteningNestedField(PropertySchema())

    @property
    def load_type(self) -> Type[dict]:
        return dict

    @pre_load
    def pre_load(self, dataset: Dataset, many: bool, **kwargs):
        print("child pre load", dataset)
        return super().pre_load(dataset, many, **kwargs)


class ParentSchema(DicomSchema):
    nested = FlatteningNestedField(ChildSchema())

    @property
    def load_type(self) -> Type[dict]:
        return dict

    @pre_load
    def pre_load(self, dataset: Dataset, many: bool, **kwargs):
        print("parent pre load", dataset)
        return super().pre_load(dataset, many, **kwargs)


class TestNesting:
    def test_nesting(self):
        # Arrange
        schema = ParentSchema()

        dataset = Dataset()
        dataset.PatientID = "patient id"

        deserialized = schema.load(dataset)

        assert deserialized["nested"]["nested"]["value"] == "patient id"
