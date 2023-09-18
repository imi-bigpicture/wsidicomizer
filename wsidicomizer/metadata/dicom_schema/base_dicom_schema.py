from abc import abstractmethod
from typing import Any, Dict, Generic, Type, TypeVar
from marshmallow import Schema, post_dump, pre_load, post_load, types
from pydicom import Dataset

from wsidicomizer.metadata.base_model import BaseModel
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    FlatteningNestedField,
)

LoadType = TypeVar("LoadType")


class DicomSchema(Schema, Generic[LoadType]):
    def dump(self, obj: LoadType, **kwargs) -> Dataset:
        dataset = super().dump(obj, **kwargs)
        assert isinstance(dataset, Dataset)
        return dataset

    def load(self, dataset: Dataset, **kwargs) -> LoadType:
        item = super().load(dataset, **kwargs)  # type: ignore
        assert isinstance(item, self.load_type)
        return item

    @property
    @abstractmethod
    def load_type(self) -> Type[LoadType]:
        raise NotImplementedError()

    @post_dump
    def post_dump(self, data: Dict[str, Any], many: bool, **kwargs):
        for field in self.fields.values():
            if isinstance(field, FlatteningNestedField):
                field.flatten(data)
        dataset = Dataset()
        dataset.update(data)  # type: ignore
        return dataset

    @pre_load
    def pre_load(self, dataset: Dataset, many: bool, **kwargs):
        attributes = {}
        for key, field in self.fields.items():
            if field.dump_only:
                continue
            if field.data_key is not None:
                key = field.data_key
            if isinstance(field, FlatteningNestedField):
                attributes[key] = field.de_flatten(dataset)
            else:
                attributes[key] = dataset.get(key, None)
        return attributes

    @post_load
    def post_load(self, data: Dict[str, Any], **kwargs):
        return self.load_type(**data)
