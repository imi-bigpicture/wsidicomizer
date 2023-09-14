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

"""Classes for representing metadata attributes as DICOM attributes."""
import datetime
from abc import abstractmethod
from dataclasses import MISSING, dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Generic, Iterable, Literal, Optional, TypeVar, Union

from pydicom import Dataset
from pydicom import Sequence as DicomSequence
from pydicom.sr.coding import Code
from pydicom.uid import UID
from pydicom.valuerep import DA, DT, IS, TM, DSdecimal, DSfloat

ValueType = TypeVar("ValueType")
FormatedType = TypeVar("FormatedType")


@dataclass
class DicomAttribute(Generic[ValueType, FormatedType]):
    """Represents a DICOM attribute.

    Parameters
    ----------
    tag: str
        DICOM tag name
    required: bool
        If attribute is required to be present in dataset, i.e. is of `Type 1` or
        `Type 2`.
    value: Optional[ValueType]
        Value for attribute.
    default: Optional[
        Union[ValueType, Callable[[], ValueType]]
    ] = None
        Default value or factory method to use for `required` attributes when `value`
        is None. Should be specified for `Type 1` attributes.

    """

    tag: str
    required: bool
    value: Optional[ValueType]
    default: Optional[Union[ValueType, Callable[[], ValueType]]] = None

    @abstractmethod
    def _formater(self, value: ValueType) -> FormatedType:
        """Return formatted value that is accepted by DataElement() for the DICOM tag."""
        raise NotImplementedError()

    def insert_into_dataset(self, dataset: Dataset) -> None:
        """Insert attribute into dataset."""
        value = None
        try:
            value = self._get_value()
            if value is MISSING:
                return
            if value is not None:
                value = self._formater(value)
            self._set_in_dataset(dataset, value)
        except Exception as exception:
            raise ValueError(
                f"Failed to insert attribute {self.tag} with value {value} due to exception",
                exception,
            )

    def _get_value(self) -> Optional[Union[ValueType, Literal[MISSING]]]:
        """
        Get value for attribute.

        If the value is None:
        - If the attribute is not required return MISSING (`Type 3`).
        - If the attribute is required but does not have a default, return None
        (`Type 2`).
        - If the attribute is required and has a default, return default (`Type 1`).

        """
        if self.value is not None:
            return self.value
        elif self.required:
            if self.default is None:
                return None
            elif isinstance(self.default, Callable):
                return self.default()
            else:
                return self.default
        return MISSING

    def _set_in_dataset(self, dataset: Dataset, value: Optional[FormatedType]) -> None:
        setattr(dataset, self.tag, value)


class DicomStringAttribute(DicomAttribute[Union[str, Enum], str]):
    def _formater(self, value: Union[str, Enum]) -> str:
        if isinstance(value, Enum):
            return value.name
        return value


class DicomListStringAttribute(
    DicomAttribute[Union[str, Iterable[str]], Iterable[str]]
):
    def _formater(self, value: Union[str, Iterable[str]]) -> Iterable[str]:
        if isinstance(value, str):
            value = [value]
        return value

    def _set_in_dataset(self, dataset: Dataset, value: Optional[Iterable[str]]):
        if value is not None or self.required:
            attribute = getattr(dataset, self.tag, list())
            if value is not None:
                attribute.extend(value)
            setattr(dataset, self.tag, attribute)


class DicomBoolAttribute(DicomAttribute[bool, Union[Literal["YES"], Literal["NO"]]]):
    def _formater(self, value: bool) -> Union[Literal["YES"], Literal["NO"]]:
        if value:
            return "YES"
        return "NO"


class DicomDateTimeAttribute(
    DicomAttribute[
        Union[datetime.datetime, datetime.date, datetime.time], Union[TM, DA, DT]
    ]
):
    def _formater(
        self, value: Union[datetime.datetime, datetime.date, datetime.time]
    ) -> Any:
        if isinstance(value, datetime.time):
            return TM(value)
        if isinstance(value, datetime.date):
            return DA(value)
        if isinstance(value, datetime.datetime):
            return DT(value)
        raise TypeError()


class DicomCodeAttribute(DicomAttribute[Code, Dataset]):
    def _formater(self, value: Code) -> Dataset:
        item = Dataset()
        item.CodeValue = value.value
        item.CodingSchemeDesignator = value.scheme_designator
        item.CodingSchemeVersion = value.scheme_version
        item.CodeMeaning = value.meaning
        return item

    def _set_in_dataset(self, dataset: Dataset, value: Optional[Dataset]):
        if value is not None or self.required:
            attribute = getattr(dataset, self.tag, DicomSequence())
            if value is not None:
                attribute.append(value)
            setattr(dataset, self.tag, attribute)


class DicomUidAttribute(DicomAttribute[UID, UID]):
    def _formater(self, value: UID) -> UID:
        return value


class DicomNumericAttributeType(Enum):
    FLOAT_STRING = "float string"
    DECIMAL_STRING = "decimal string"
    INTEGER_STRING = "integer string"
    NOT_STRING = "not string"


@dataclass
class DicomNumericAttribute(DicomAttribute[Union[int, float], Union[int, float, str]]):
    number_type: DicomNumericAttributeType = DicomNumericAttributeType.NOT_STRING

    def _formater(self, value: Union[int, float]) -> Any:
        if self.number_type == DicomNumericAttributeType.FLOAT_STRING:
            return DSfloat(value, True)
        if self.number_type == DicomNumericAttributeType.DECIMAL_STRING:
            return DSdecimal(str(value), True)
        if self.number_type == DicomNumericAttributeType.INTEGER_STRING:
            return IS(value)
        return value


class DicomByteAttribute(DicomAttribute[bytes, bytes]):
    def _formater(self, value: bytes) -> bytes:
        return value


class DicomSequenceAttribute(DicomAttribute[Iterable[DicomAttribute], DicomSequence]):
    def _formater(self, value: Iterable[DicomAttribute]) -> DicomSequence:
        sequence = DicomSequence()
        for attribute in value:
            dataset = Dataset()
            attribute.insert_into_dataset(dataset)
            sequence.append(dataset)
        return sequence
