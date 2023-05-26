from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Union,
    TypeVar,
    Generic,
)

from pydicom import Dataset
from pydicom.sr.coding import Code
from wsidicom.instance import ImageType
from pydicom.uid import UID, generate_uid

DicomAttributeValueType = TypeVar("DicomAttributeValueType")


@dataclass
class DicomAttribute(Generic[DicomAttributeValueType]):
    """Represents a DICOM attribute.

    Parameters
    ----------
    key: str
        DICOM key name
    required: bool:
        If attribute is required to be present in dataset, i.e. is of type 1 or 2.
    value: Optional[DicomAttributeValueType]:
        Value for attribute.
    default_factory: Optional[Callable[[], DicomAttributeValueType]] = None
        Method to call to generate a default value for required attributes that cant
        have an emtpy value, i.e. is of type 1.
    formater: Optional[
        Callable[[DicomAttributeValueType], DicomAttributeValueType]
    ] = None
        Method to call to format the attribute value before writing to dataset.

    """

    key: str
    required: bool
    value: Optional[DicomAttributeValueType]
    default_factory: Optional[Callable[[], DicomAttributeValueType]] = None
    formater: Optional[Callable[[DicomAttributeValueType], Any]] = None


class DicomStringAttribute(DicomAttribute[str]):
    pass


class DicomListStringAttribute(DicomAttribute[Iterable[str]]):
    pass


class DicomDateTimeAttribute(
    DicomAttribute[Union[datetime.datetime, datetime.date, datetime.time]]
):
    pass


class DicomCodeAttribute(DicomAttribute[Code]):
    pass


class DicomUidAttribute(DicomAttribute[UID]):
    pass


class DicomNumberAttribute(DicomAttribute[Union[int, float]]):
    pass


class DicomByteAttribute(DicomAttribute[bytes]):
    pass


class DicomModelBase(metaclass=ABCMeta):
    """Base model.

    By default metadata from the file is prioritized before values provided in the
    model. To override this behavior for a specific attribute (e.g. do not take the
    value from file) add the attribute name to the to the `overrides` attribute.

    Additional attributes not defined in the model can be added in the
    `additional_attributes` dictionary with the DICOM keyword as key.
    """

    additional_attributes: Optional[Dict[str, Any]] = None
    overrides: Optional[Sequence[str]] = None
    _dicom_attributes: Iterable[Optional[DicomAttribute]]

    @abstractmethod
    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        raise NotImplementedError()

    @property
    def dicom_attributes(self) -> Iterable[DicomAttribute]:
        return (
            attribute for attribute in self._dicom_attributes if attribute is not None
        )

    def _insert_dicom_attributes_into_dataset(self, dataset: Dataset) -> None:
        for attribute in self.dicom_attributes:
            if (
                attribute.value is None
                and attribute.required
                and attribute.default_factory is not None
            ):
                attribute = attribute.default_factory()
            if attribute.formater is not None and attribute.value is not None:
                attribute = attribute.formater(attribute)
            setattr(dataset, attribute.key, attribute)

    @staticmethod
    def _bool_to_literal(value: bool) -> Union[Literal["YES"], Literal["NO"]]:
        if value:
            return "YES"
        return "NO"

    @staticmethod
    def _code_to_code_sequence_item(value: Code) -> Dataset:
        dataset = Dataset()
        dataset.CodeValue = value.value
        dataset.CodingSchemeDesignator = value.scheme_designator
        dataset.CodingSchemeVersion = value.scheme_version
        dataset.CodeMeaning = value.meaning
        return dataset

    def _default_string_value(self) -> str:
        return "Unknown"

    def _default_datetime_value(self) -> datetime.datetime:
        return datetime.datetime(1, 1, 1)

    def _format_datetime_value(
        self, value: Union[datetime.date, datetime.time, datetime.datetime]
    ) -> str:
        return value.strftime("%Y%m%d%H%M%S.%f")
