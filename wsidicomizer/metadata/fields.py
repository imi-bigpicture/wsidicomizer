"""Factory for creating fiels with json encoders and decoders."""
import datetime
from dataclasses import field
from typing import Any, Optional, Type, Union

from dataclasses_json import config as dataclasses_json_config
from pydicom.sr.coding import Code
from pydicom.uid import UID
from wsidicom.conceptcode import CidConceptCode, CidConceptCodeType


class FieldFactory:
    @classmethod
    def date_field(cls):
        return field(
            metadata=dataclasses_json_config(
                encoder=lambda x: datetime.date.isoformat(x) if x is not None else None,
                decoder=lambda x: datetime.date.fromisoformat(x)
                if x is not None
                else None,
            ),
            default=None,
        )

    @classmethod
    def time_field(cls):
        return field(
            metadata=dataclasses_json_config(
                encoder=lambda x: datetime.time.isoformat(x) if x is not None else None,
                decoder=lambda x: datetime.time.fromisoformat(x)
                if x is not None
                else None,
            ),
            default=None,
        )

    @classmethod
    def datetime_field(cls):
        return field(
            metadata=dataclasses_json_config(
                encoder=lambda x: datetime.datetime.isoformat(x)
                if x is not None
                else None,
                decoder=lambda x: datetime.datetime.fromisoformat(x)
                if x is not None
                else None,
            ),
            default=None,
        )

    @classmethod
    def uid_field(cls, default: Optional[UID] = None):
        return field(metadata=dataclasses_json_config(decoder=UID), default=default)

    @classmethod
    def string_or_code_field(cls):
        return field(
            metadata=dataclasses_json_config(
                encoder=cls._encode_string_or_code,
                decoder=cls._decode_string_or_code,
            ),
            default=None,
        )

    @classmethod
    def list_string_or_code_field(cls):
        return field(
            metadata=dataclasses_json_config(
                encoder=lambda x: [cls._encode_string_or_code(item) for item in x],
                decoder=lambda x: [cls._decode_string_or_code(item) for item in x],
            ),
            default_factory=list,
        )

    @classmethod
    def list_code_field(cls):
        return field(
            metadata=dataclasses_json_config(
                encoder=lambda x: [cls._encode_code(item) for item in x],
                decoder=lambda x: [cls._decode_code(item) for item in x],
            ),
            default_factory=list,
        )

    @classmethod
    def float_or_code_field(
        cls,
    ):
        return field(
            metadata=dataclasses_json_config(
                encoder=cls._encode_float_or_code,
                decoder=cls._decode_float_or_code,
            ),
            default=None,
        )

    @classmethod
    def code_field(cls, default: Optional[Code] = None):
        return field(
            metadata=dataclasses_json_config(
                encoder=cls._encode_code,
                decoder=cls._decode_code,
            ),
            default=default,
        )

    @classmethod
    def concept_code_field(
        cls,
        type: Type[CidConceptCodeType],
        default: Optional[CidConceptCodeType] = None,
    ):
        return field(
            metadata=dataclasses_json_config(
                encoder=cls._encode_code,
                decoder=lambda x: cls._decode_concept_codecode(type, x),
            ),
            default=default,
        )

    @classmethod
    def float_or_concent_code_field(
        cls,
        type: Type[CidConceptCodeType],
        default: Optional[CidConceptCodeType] = None,
    ):
        return field(
            metadata=dataclasses_json_config(
                encoder=cls._encode_float_or_code,
                decoder=lambda x: cls._decode_concept_codecode(type, x),
            ),
            default=default,
        )

    @classmethod
    def list_concept_code_field(
        cls,
        type: Type[CidConceptCodeType],
    ):
        return field(
            metadata=dataclasses_json_config(
                encoder=lambda x: [cls._encode_code(item) for item in x],
                decoder=lambda x: [
                    cls._decode_concept_codecode(type, item) for item in x
                ],
            ),
            default_factory=list,
        )

    @classmethod
    def point_mm_field(cls):
        return field(metadata=dataclasses_json_config())

    @classmethod
    def _encode_float_or_code(cls, value: Union[float, Code]):
        if isinstance(value, (Code, CidConceptCode)):
            return cls._encode_code(value)
        return value

    @classmethod
    def _decode_float_or_code(cls, value: Any):
        try:
            return cls._decode_code(value)
        except Exception as excption:
            return float(value)

    @classmethod
    def _encode_string_or_code(cls, value: Union[str, Code]):
        if isinstance(value, Code):
            return cls._encode_code(value)
        return value

    @staticmethod
    def _encode_code(value: Optional[Union[Code, CidConceptCode]]):
        if value is None:
            return None
        return {
            "value": value.value,
            "scheme_designator": value.scheme_designator,
            "meaning": value.meaning,
            "scheme_version": value.scheme_version,
        }

    @classmethod
    def _decode_string_or_code(cls, value: Any):
        try:
            return cls._decode_code(value)
        except Exception as excption:
            return value

    @staticmethod
    def _decode_code(value: Any):
        if value is None:
            return None
        return Code(**value)

    @staticmethod
    def _decode_concept_codecode(type: Type[CidConceptCodeType], value: Any):
        if value is None:
            return None
        return type(**value)
