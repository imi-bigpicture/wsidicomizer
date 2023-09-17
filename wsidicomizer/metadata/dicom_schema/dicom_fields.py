import datetime
import datetime as dt
from enum import Enum as EnumType
import math
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from marshmallow.utils import missing
from marshmallow import Schema, fields, post_dump, pre_load, types
from marshmallow.base import SchemaABC
from marshmallow.fields import Field
from marshmallow.utils import missing as missing_
from pydicom import DataElement, Dataset
from pydicom.multival import MultiValue
from pydicom.sr.coding import Code
from pydicom.uid import UID
from pydicom.valuerep import DA, DT, TM, DSfloat, PersonName
from wsidicom.conceptcode import ConceptCode
from wsidicom.geometry import Orientation, PointMm
from pydicom.sequence import Sequence as DicomSequence
from wsidicomizer.metadata.defaults import Defaults
from wsidicomizer.metadata.dicom_schema.dicom_constants import DicomBoolean


class DateTimeDicomField(fields.Field):
    def _serialize(
        self,
        value: Optional[datetime.datetime],
        attr: Optional[str],
        obj: Any,
        **kwargs,
    ):
        if value is None:
            return None
        return DT(value)


class DateDicomField(fields.Field):
    def _serialize(
        self, value: Optional[datetime.date], attr: Optional[str], obj: Any, **kwargs
    ):
        if value is None:
            return None
        return DA(value)


class TimeDicomField(fields.Field):
    def _serialize(
        self, value: Optional[datetime.time], attr: Optional[str], obj: Any, **kwargs
    ):
        if value is None:
            return None
        return TM(value)


class BooleanDicomField(fields.Boolean):
    def __init__(self, **kwargs):
        super().__init__(truthy=set(["YES"]), falsy=set(["NO"]), **kwargs)

    def _serialize(self, value: bool, attr: Optional[str], obj: Any, **kwargs):
        if value:
            string_value = self.truthy
        else:
            string_value = self.falsy
        return list(string_value)[0]


class OffsetInSlideCoordinateSystemField(fields.Field):
    def _serialize(
        self, origin: Optional[PointMm], attr: Optional[str], obj: Any, **kwargs
    ):
        if origin is None:
            if self.dump_default is None:
                return None
            assert isinstance(self.dump_default, PointMm)
            origin = self.dump_default
        origin_element = Dataset()
        origin_element.XOffsetInSlideCoordinateSystem = DSfloat(origin.x, True)
        origin_element.YOffsetInSlideCoordinateSystem = DSfloat(origin.y, True)
        return [origin_element]

    def _deserialize(
        self,
        value: DataElement,
        attr: Optional[str],
        data: Optional[Dict[str, Any]],
        **kwargs,
    ) -> PointMm:
        return PointMm(
            x=value[0].XOffsetInSlideCoordinateSystem,
            y=value[0].YOffsetInSlideCoordinateSystem,
        )


class ImageOrientationSlideField(fields.Field):
    def _serialize(
        self, rotation: Optional[float], attr: Optional[str], obj: Any, **kwargs
    ):
        if rotation is None:
            if self.dump_default is None:
                return None
            assert isinstance(self.dump_default, float)
            rotation = self.dump_default
        x = round(math.sin(rotation * math.pi / 180), 8)
        y = round(math.cos(rotation * math.pi / 180), 8)
        return [-x, y, 0, y, x, 0]

    def _deserialize(
        self,
        value: Tuple[float, float, float, float, float, float],
        attr: Optional[str],
        data: Optional[Dict[str, Any]],
        **kwargs,
    ) -> float:
        orientation = Orientation(value)
        return orientation.rotation


class ListDicomField(fields.List):
    """Wrapper around normala list that handles single-valued lists from pydicom."""

    def _deserialize(
        self, value: Union[Any, List[Any]], attr, data, **kwargs
    ) -> List[Any]:
        if not isinstance(value, MultiValue):
            value = [value]
        return super()._deserialize(value, attr, data, **kwargs)


class FlatteningNestedField(fields.Nested):
    def __init__(self, nested: Schema, **kwargs):
        self._nested = nested
        super().__init__(nested=nested, **kwargs)

    @property
    def nested_schema(self) -> Schema:
        return self._nested

    def de_flatten(self, dataset: Dataset) -> Dataset:
        nested = Dataset()
        for nested_field in self.nested_schema.fields.values():
            if nested_field.dump_only:
                continue
            if isinstance(nested_field, FlatteningNestedField):
                nested.update(nested_field.de_flatten(dataset))
            elif nested_field.data_key is not None:
                nested_value = dataset.pop(nested_field.data_key, None)
                # TODO is this correct?
                if nested_value is not None:
                    nested[nested_field.data_key] = nested_value
        if len(nested) == 0:
            return None
        return nested

    def flatten(self, data: Dict[str, Any]):
        key = self.name
        if self.data_key is not None:
            key = self.data_key
        nested = data.pop(key, None)
        if isinstance(nested, Dataset):
            for nested_key, nested_value in nested.items():
                data[nested_key] = nested_value  # type: ignore

    def _serialize(self, nested_obj, attr, obj, **kwargs):
        if nested_obj is None and self.dump_default != missing:
            nested_obj = self.dump_default
        return super()._serialize(nested_obj, attr, obj, **kwargs)


CodeType = TypeVar("CodeType", Code, ConceptCode)


class FloatDicomField(fields.Float):
    def _serialize(self, value: float, attr: Optional[str], obj: Any, **kwargs):
        return DSfloat(value)


class CodeDicomField(fields.Field, Generic[CodeType]):
    def __init__(self, load_type: Type[CodeType], **kwargs) -> None:
        self._load_type = load_type
        super().__init__(**kwargs)

    def _serialize(
        self, value: Optional[CodeType], attr: Optional[str], obj: Any, **kwargs
    ):
        if value is None:
            return self.dump_default
        dataset = Dataset()
        dataset.CodeValue = value.value
        dataset.CodingSchemeDesignator = value.scheme_designator
        dataset.CodeMeaning = value.meaning
        dataset.CodingSchemeVersion = value.scheme_version

        return dataset

    def _deserialize(
        self,
        value: Dataset,
        attr: Optional[str],
        data: Optional[Dict[str, Any]],
        **kwargs,
    ):
        return self._load_type(
            value.CodeValue,
            value.CodingSchemeDesignator,
            value.CodeMeaning,
            value.get("CodingSchemeVersion", None),
        )


class SingleCodeDicomField(CodeDicomField):
    def _serialize(self, value: CodeType, attr: Optional[str], obj: Any, **kwargs):
        return [super()._serialize(value, attr, obj, **kwargs)]

    def _deserialize(
        self,
        value: Sequence[Dataset],
        attr: Optional[str],
        data: Optional[Dict[str, Any]],
        **kwargs,
    ):
        return super()._deserialize(value[0], attr, data, **kwargs)


class FloatOrCodeDicomField(fields.Field, Generic[CodeType]):
    def __init__(self, load_type: Type[CodeType], **kwargs) -> None:
        self._float_field = FloatDicomField()
        self._code_field = CodeDicomField(load_type)
        super().__init__(**kwargs)

    def _serialize(self, value: Union[float, CodeType], attr, obj, **kwargs):
        if isinstance(value, float):
            return self._float_field.serialize(attr, obj, **kwargs)
        return self._code_field.serialize(attr, obj, **kwargs)

    def _deserialize(self, value: Union[DSfloat, Dataset], attr, data, **kwargs):
        if isinstance(value, DSfloat):
            return self._float_field.deserialize(value, attr, data, **kwargs)
        return self._code_field.deserialize(value, attr, data, **kwargs)


class UidDicomField(fields.Field):
    pass


class PatientNameDicomField(fields.String):
    def _deserialize(self, value: PersonName, attr, data, **kwargs) -> Any:
        return str(value)


ValueType = TypeVar("ValueType")


class TypeDicomField(fields.Field, Generic[ValueType]):
    def __init__(self, nested: Field, **kwargs):
        self._nested = nested
        super().__init__(**kwargs)

    def _serialize(self, value: Optional[ValueType], attr, obj, **kwargs):
        return self._nested._serialize(value, attr, obj, **kwargs)

    def _deserialize(self, value: Any, attr, data, **kwargs):
        return self._nested._deserialize(value, attr, data, **kwargs)


class DefaultingDicomField(TypeDicomField[ValueType]):
    """Wrapper around a field that should always be present and have a value."""

    def __init__(self, nested: Field, dump_default: ValueType, **kwargs):
        self._dump_default = dump_default
        super().__init__(nested=nested, dump_default=dump_default, **kwargs)

    def _serialize(self, value: Optional[ValueType], attr, obj, **kwargs):
        if value is None:
            value = self._dump_default
        return super()._serialize(value, attr, obj, **kwargs)


class DefaultingTagDicomField(TypeDicomField[ValueType]):
    """Wrapper around a field that should always be present and have a value. Takes
    default value from attribute in object."""

    def __init__(self, nested: Field, tag: str, **kwargs):
        self._tag = tag
        super().__init__(nested=nested, **kwargs)

    def _serialize(self, value: Optional[ValueType], attr, obj, **kwargs):
        if value is None:
            value = getattr(obj, self._tag)
        return super()._serialize(value, attr, obj, **kwargs)


class NoneDicomField(TypeDicomField):
    """Wrapper around a field that should always be present but can be empty."""


class NotNoneDicomField(TypeDicomField[ValueType]):
    """Wrapper around a field that does not always need be present."""

    def _serialize(self, value: Optional[ValueType], attr, obj, **kwargs):
        if value is None:
            raise ValueError("Should not serialize a Type3 field with no value")
        return super()._serialize(value, attr, obj, **kwargs)


class SequenceWrappingField(fields.Field, Generic[ValueType]):
    def __init__(self, nested: Field, **kwargs):
        self._nested = nested
        super().__init__(**kwargs)

    def _serialize(self, value: Optional[ValueType], attr, obj, **kwargs):
        dataset = Dataset()
        nested_value = self._nested._serialize(value, attr, obj, **kwargs)
        if self._nested.data_key is not None:
            key = self._nested.data_key
        else:
            key = self._nested.name
        setattr(dataset, key, nested_value)
        return [dataset]

    def _deserialize(self, value: Sequence[Dataset], attr, data, **kwargs):
        if self._nested.data_key is not None:
            key = self._nested.data_key
        else:
            key = self._nested.name
        nested_value = getattr(value[0], key)
        return self._nested._deserialize(nested_value, attr, data, **kwargs)
