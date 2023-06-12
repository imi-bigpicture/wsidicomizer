"""Base model for metadata."""
import json
from abc import ABCMeta, abstractmethod
from copy import copy
from dataclasses import dataclass, fields
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Type,
    TypeVar,
)

from dataclasses_json import dataclass_json
from pydicom import Dataset
from wsidicom.instance import ImageType

from wsidicomizer.metadata.dicom_attribute import DicomAttribute

ModelBaseType = TypeVar("ModelBaseType", bound="ModelBase")


@dataclass_json
@dataclass
class ModelBase(metaclass=ABCMeta):
    """Base model.

    By default metadata from the file is prioritized before values provided in the
    model. To override this behavior for a specific attribute (e.g. do not take the
    value from file) add the attribute name to the to the `overrides` attribute.

    Additional attributes not defined in the model can be added in the
    `additional_attributes` dictionary with the DICOM tag as key.
    """

    @property
    def overrides(self) -> Optional[Dict[str, bool]]:
        """
        Attributes that this instance should override when merging with other instance.

        The key should be the attribute name. A true value specifies that the override
        should be forced, e.g. the attribute should override even if it is None.
        """
        return None

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
        cls: Type[ModelBaseType],
        high: Optional[ModelBaseType],
        low: Optional[ModelBaseType],
    ) -> Optional[ModelBaseType]:
        """
        Merge two models to a new model.

        The high-model is prioritized prior to the low-model unless the attribute is
        specified in the override dictionary of the low-model. For forced override the
        low is used even if it is None.
        """
        if high is None and low is None:
            return None
        if high is not None and low is None:
            return copy(high)
        if high is None and low is not None:
            return copy(low)
        assert high is not None and low is not None
        attributes: Dict[str, Any] = {}
        for field in fields(cls):
            high_value = getattr(high, field.name, None)
            low_value = getattr(low, field.name, None)
            if isinstance(field.type, ModelBase):
                value = ModelBase.merge(high_value, low_value)
            elif high_value is None and low_value is not None:
                value = low_value
            elif (
                low.overrides is not None
                and field.name in low.overrides
                and (high_value is None or low.overrides[field.name])
            ):
                value = low_value
            else:
                value = high_value
            attributes[field.name] = value
        return cls(**attributes)
