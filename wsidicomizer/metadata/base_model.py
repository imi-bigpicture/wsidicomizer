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

"""Base model for metadata."""
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, fields
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Type,
    TypeVar,
)

from pydicom import Dataset
from wsidicom.instance import ImageType

from wsidicomizer.metadata.dicom_attribute import DicomAttribute

BaseModelType = TypeVar("BaseModelType", bound="BaseModel")


@dataclass
class BaseModel(metaclass=ABCMeta):
    """Base model.

    Additional attributes not defined in the model can be added in the
    `additional_attributes` dictionary with the DICOM tag as key.
    """

    @property
    def additional_attribute(self) -> Optional[Dict[str, DicomAttribute]]:
        """Additional attributes."""
        return None

    @abstractmethod
    def insert_into_dataset(
        self,
        dataset: Dataset,
        image_type: ImageType,
    ) -> None:
        """Convert the model into DicomAttributes and insert them into the dataset."""
        raise NotImplementedError()

    @staticmethod
    def _insert_dicom_attributes_into_dataset(
        dataset: Dataset, attributes: Iterable[DicomAttribute]
    ):
        """Insert list of DicomAttributes into dataset."""
        for attribute in attributes:
            attribute.insert_into_dataset(dataset)

    @classmethod
    def merge(
        cls: Type[BaseModelType],
        base: Optional[BaseModelType],
        user: Optional[BaseModelType],
        default: Optional[BaseModelType],
    ) -> Optional[BaseModelType]:
        """
        Merge three models to a new model.
        - base - model from file.
        - user - user defined model that overrides base.
        - default - user defined model with default values used for fields not defined
        in base or user model.

        """
        not_none = [model for model in [user, base, default] if model is not None]
        if len(not_none) == 0:
            return None
        if len(not_none) == 1:
            return not_none[0]
        attributes: Dict[str, Any] = {}
        for field in fields(cls):
            base_value = getattr(base, field.name, None)
            user_value = getattr(user, field.name, None)
            default_value = getattr(default, field.name, None)
            value = next(
                (
                    value
                    for value in [user_value, base_value, default_value]
                    if value is not None
                ),
                None,
            )
            if isinstance(value, BaseModel):
                value = value.merge(base_value, user_value, default_value)

            attributes[field.name] = value
        return cls(**attributes)
