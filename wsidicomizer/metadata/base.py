import datetime
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Sequence, Tuple, Union

from pydicom import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.sr.coding import Code
from pydicom.uid import UID

from wsidicomizer.metadata.util import code_to_dataset


@dataclass
class DicomModelBase:
    pass

    def to_dataset(self) -> Dataset:
        dataset = Dataset()
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None:
                setattr(
                    dataset, self._field_name_to_dicom_attribute_name(field.name), None
                )
            elif isinstance(value, (str, datetime.date)):
                (dicom_name, value) = self._simple_attribute(field.name, value)
                setattr(dataset, dicom_name, value)
            elif isinstance(value, list):
                values = self._list_attribute(field.name, value)
                for (dicom_name, dicom_value) in values.items():
                    setattr(dataset, dicom_name, dicom_value)
            else:
                raise NotImplementedError(
                    f"Not implemented handling of field {field.name}"
                    f"with value {type(value)}"
                )

        return dataset

    @classmethod
    def _simple_attribute(
        cls, field_name: str, value: Union[str, UID, datetime.date, Code]
    ) -> Tuple[str, Any]:
        if isinstance(value, Code):
            return (
                cls._field_name_to_dicom_attribute_name(field_name, True),
                DicomSequence([code_to_dataset(value)]),
            )
        return (
            cls._field_name_to_dicom_attribute_name(field_name),
            value,
        )

    @classmethod
    def _list_attribute(
        cls, field_name: str, values: Sequence[Any]
    ) -> Dict[str, Union[List[str], DicomSequence]]:
        items = {}
        string_values = [value for value in values if isinstance(value, str)]
        if len(string_values) > 0:
            items[cls._field_name_to_dicom_attribute_name(field_name)] = string_values
        code_values = [
            code_to_dataset(value) for value in values if isinstance(value, Code)
        ]
        if len(code_values) > 0:
            items[
                cls._field_name_to_dicom_attribute_name(field_name, True)
            ] = code_values
        return items

    @staticmethod
    def _field_name_to_dicom_attribute_name(
        field_name: str, is_code_sequence: bool = False
    ) -> str:
        field_name = field_name.title().replace("_", "")
        if field_name.endswith("Uid"):
            field_name, _ = field_name.rsplit("Uid", 1)
            field_name += "UID"
        elif field_name.endswith("Id"):
            field_name, _ = field_name.rsplit("Id", 1)
            field_name += "ID"
        elif is_code_sequence:
            field_name += "CodeSequence"
        return field_name
