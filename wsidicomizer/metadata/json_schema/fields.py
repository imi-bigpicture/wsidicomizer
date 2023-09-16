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

import dataclasses
from typing import Any, Dict, Mapping, Optional, Type, Union

from marshmallow import ValidationError, fields
from pydicom.sr.coding import Code
from pydicom.uid import UID
from wsidicom.conceptcode import CidConceptCode, CidConceptCodeType
from wsidicom.geometry import PointMm

from wsidicomizer.metadata.sample import (
    SlideSamplePosition,
    Specimen,
    SpecimenIdentifier,
)


class SlideSamplePositionJsonField(fields.Field):
    def _serialize(
        self, value: Optional[Union[str, SlideSamplePosition]], attr, obj, **kwargs
    ) -> Optional[Union[str, Dict]]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return {
            "x": value.x,
            "y": value.y,
            "z": value.z,
        }

    def _deserialize(
        self,
        value: Union[str, Dict],
        attr: Optional[str],
        data: Optional[Mapping[str, Any]],
        **kwargs,
    ) -> Union[str, SlideSamplePosition]:
        try:
            if isinstance(value, str):
                return value
            return SlideSamplePosition(value["x"], value["y"], value["z"])
        except ValueError as error:
            raise ValidationError(
                "Could not deserialize slide sample position."
            ) from error


class SpecimenIdentifierJsonField(fields.Field):
    def _serialize(
        self,
        value: Optional[Union[Specimen, str, SpecimenIdentifier]],
        attr,
        obj,
        **kwargs,
    ) -> Optional[Union[str, Dict]]:
        if value is None:
            return None
        if isinstance(value, Specimen):
            return self._serialize(value.identifier, attr, obj, **kwargs)
        if isinstance(value, str):
            return value
        return {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(value)
            if getattr(value, field.name) is not None
        }

    def _deserialize(
        self,
        value: Union[str, Dict],
        attr: Optional[str],
        data: Optional[Mapping[str, Any]],
        **kwargs,
    ) -> Union[str, SpecimenIdentifier]:
        try:
            if isinstance(value, str):
                return value
            return SpecimenIdentifier(**value)
        except ValueError as error:
            raise ValidationError(
                "Could not deserialize specimen identifier."
            ) from error


class PointMmJsonField(fields.Field):
    def _serialize(
        self, value: Optional[PointMm], attr, obj, **kwargs
    ) -> Optional[Dict]:
        if value is None:
            return None
        return {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(value)
        }

    def _deserialize(
        self,
        value: Dict,
        attr: Optional[str],
        data: Optional[Mapping[str, Any]],
        **kwargs,
    ) -> PointMm:
        try:
            return PointMm(**value)
        except ValueError as error:
            raise ValidationError("Could not deserialize PointMm.") from error


class UidJsonField(fields.Field):
    def _serialize(self, value: Optional[UID], attr, obj, **kwargs) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def _deserialize(self, value: str, attr, data, **kwargs) -> UID:
        try:
            return UID(value)
        except ValueError as error:
            raise ValidationError("Could not deserialize UID.") from error


class CodeJsonField(fields.Field):
    def _serialize(self, value: Optional[Code], attr, obj, **kwargs) -> Optional[Dict]:
        if value is None:
            return None
        return JsonFieldFactory._serialize_code(value)

    def _deserialize(self, value: Dict, attr, data, **kwargs) -> Code:
        try:
            return Code(**value)
        except ValueError as error:
            raise ValidationError("Could not deserialize Code.") from error


class StringOrCodeJsonField(fields.Field):
    def _serialize(
        self, value: Optional[Union[str, Code]], attr, obj, **kwargs
    ) -> Optional[Union[str, Dict]]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        code = {
            "value": value.value,
            "scheme_designator": value.scheme_designator,
            "meaning": value.meaning,
        }
        if value.scheme_version is not None:
            code["scheme_version"] = value.scheme_version
        return code

    def _deserialize(
        self, value: Union[str, Dict], attr, data, **kwargs
    ) -> Union[str, Code]:
        if isinstance(value, str):
            return value
        try:
            return Code(**value)
        except ValueError as error:
            raise ValidationError("Could not deserialize Code.") from error


class JsonFieldFactory:
    @classmethod
    def float_or_concept_code(
        cls, concept_code_type: Type[CidConceptCodeType], many=False, **metadata
    ) -> Type[fields.Field]:
        def serialize(
            self, value: Optional[Union[float, CidConceptCodeType]], attr, obj, **kwargs
        ) -> Optional[Union[float, Dict]]:
            if value is None:
                return None
            if isinstance(value, float):
                return value
            return cls._serialize_code(value)

        def deserialize(
            self,
            value: Union[float, Dict],
            attr: Optional[str],
            data: Optional[Mapping[str, Any]],
            **kwargs,
        ) -> Union[float, CidConceptCodeType]:
            if isinstance(value, float):
                return value
            try:
                return concept_code_type(**value)
            except ValueError as error:
                raise ValidationError("Could not deserialize Code.") from error

        return type(
            f"FloatOr{CidConceptCodeType}Field",
            (fields.Field,),
            {"_serialize": serialize, "_deserialize": deserialize},
        )

    @classmethod
    def str_or_concept_code(
        cls, concept_code_type: Type[CidConceptCodeType], many=False, **metadata
    ) -> Type[fields.Field]:
        def serialize(
            self, value: Optional[Union[str, CidConceptCodeType]], attr, obj, **kwargs
        ) -> Optional[Union[str, Dict]]:
            if value is None:
                return None
            if isinstance(value, str):
                return value

            return cls._serialize_code(value)

        def deserialize(
            self,
            value: Union[str, Dict],
            attr: Optional[str],
            data: Optional[Mapping[str, Any]],
            **kwargs,
        ) -> Union[str, CidConceptCodeType]:
            if isinstance(value, str):
                return value
            try:
                return concept_code_type(**value)
            except ValueError as error:
                raise ValidationError("Could not deserialize Code.") from error

        return type(
            f"StringOr{CidConceptCodeType}Field",
            (fields.Field,),
            {"_serialize": serialize, "_deserialize": deserialize},
        )

    @classmethod
    def concept_code(
        cls,
        concept_code_type: Type[CidConceptCodeType],
    ) -> Type[fields.Field]:
        def serialize(
            self, value: Optional[CidConceptCodeType], attr, obj, **kwargs
        ) -> Optional[Dict]:
            if value is None:
                return None
            return cls._serialize_code(value)

        deserialize = cls._concept_code_deserializer_factory(concept_code_type)

        return type(
            f"{CidConceptCodeType}Field",
            (fields.Field,),
            {"_serialize": serialize, "_deserialize": deserialize},
        )

    @staticmethod
    def _concept_code_deserializer_factory(
        concept_code_type: Type[CidConceptCodeType],
    ):
        def _deserialize(
            self,
            value: Dict,
            attr: Optional[str],
            data: Optional[Mapping[str, Any]],
            **kwargs,
        ) -> CidConceptCodeType:
            try:
                return concept_code_type(**value)
            except ValueError as error:
                raise ValidationError("Could not deserialize Code.") from error

        return _deserialize

    @staticmethod
    def _serialize_code(code: Union[Code, CidConceptCode]) -> Dict[str, str]:
        try:
            result = {
                "value": code.value,
                "scheme_designator": code.scheme_designator,
                "meaning": code.meaning,
            }
            if code.scheme_version is not None:
                result["scheme_version"] = code.scheme_version
            return result

        except Exception as exception:
            raise ValueError(f"Failed to serialize code {code}") from exception
