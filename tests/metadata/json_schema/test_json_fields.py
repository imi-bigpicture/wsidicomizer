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

from typing import Dict, Union
import pytest
from tests.metadata.helpers import assert_dict_equals_code
from wsidicomizer.metadata.sample import SlideSamplePosition, SpecimenIdentifier
from wsidicomizer.metadata.json_schema.fields import (
    CodeJsonField,
    JsonFieldFactory,
    PointMmJsonField,
    SlideSamplePositionJsonField,
    SpecimenIdentifierJsonField,
    StringOrCodeJsonField,
    UidJsonField,
)
from wsidicom.geometry import PointMm
from pydicom.uid import UID
from pydicom.sr.coding import Code
from wsidicom.conceptcode import IlluminationColorCode


class TestFields:
    @pytest.mark.parametrize(
        "slide_sample_position", ["position", SlideSamplePosition(1, 2, 3)]
    )
    def test_slide_sample_position_serialize(
        self, slide_sample_position: Union[str, SlideSamplePosition]
    ):
        # Arrange

        # Act
        dumped = SlideSamplePositionJsonField()._serialize(
            slide_sample_position, None, None
        )

        # Assert
        if isinstance(slide_sample_position, str):
            assert dumped == slide_sample_position
        else:
            assert isinstance(dumped, dict)
            assert dumped["x"] == slide_sample_position.x
            assert dumped["y"] == slide_sample_position.y
            assert dumped["z"] == slide_sample_position.z

    @pytest.mark.parametrize(
        "slide_sample_position", ["position", {"x": 1, "y": 2, "z": 3}]
    )
    def test_slide_sample_position_deserialize(
        self, slide_sample_position: Union[str, Dict[str, float]]
    ):
        # Arrange

        # Act
        loaded = SlideSamplePositionJsonField()._deserialize(
            slide_sample_position, None, None
        )

        # Assert
        if isinstance(slide_sample_position, str):
            assert loaded == slide_sample_position
        else:
            assert isinstance(loaded, SlideSamplePosition)
            assert loaded.x == slide_sample_position["x"]
            assert loaded.y == slide_sample_position["y"]
            assert loaded.z == slide_sample_position["z"]

    @pytest.mark.parametrize(
        "identifier",
        ["identifier", SpecimenIdentifier("identifier", "issuer", "issuer type")],
    )
    def test_specimen_identifier_serialize(
        self, identifier: Union[str, SpecimenIdentifier]
    ):
        # Arrange

        # Act
        dumped = SpecimenIdentifierJsonField()._serialize(identifier, None, None)

        # Assert
        if isinstance(identifier, str):
            assert dumped == identifier
        else:
            assert isinstance(dumped, dict)
            assert dumped["value"] == identifier.value
            assert dumped["issuer"] == identifier.issuer
            assert dumped["issuer_type"] == identifier.issuer_type

    @pytest.mark.parametrize(
        "identifier",
        [
            "identifier",
            {"value": "identifier", "issuer": "issuer", "issuer_type": "issuer type"},
        ],
    )
    def test_specimen_identifier_deserialize(
        self, identifier: Union[str, Dict[str, str]]
    ):
        # Arrange

        # Act
        loaded = SpecimenIdentifierJsonField()._deserialize(identifier, None, None)

        # Assert
        if isinstance(identifier, str):
            assert loaded == identifier
        else:
            assert isinstance(loaded, SpecimenIdentifier)
            assert loaded.value == identifier["value"]
            assert loaded.issuer == identifier["issuer"]
            assert loaded.issuer_type == identifier["issuer_type"]

    def test_point_mm_serialize(self):
        # Arrange
        point = PointMm(1.0, 2.0)

        # Act
        dumped = PointMmJsonField()._serialize(point, None, None)

        # Assert
        assert isinstance(dumped, dict)
        assert dumped["x"] == point.x
        assert dumped["y"] == point.y

    def test_point_mm_deserialize(self):
        # Arrange
        dumped = {"x": 1.0, "y": 2.0}

        # Act
        loaded = PointMmJsonField()._deserialize(dumped, None, None)

        # Assert
        assert isinstance(loaded, PointMm)
        assert loaded.x == dumped["x"]
        assert loaded.y == dumped["y"]

    def test_uid_serialize(self):
        # Arrange
        uid = UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423")

        # Act
        dumped = UidJsonField()._serialize(uid, None, None)

        # Assert
        assert dumped == str(uid)

    def test_uid_deserialize(self):
        # Arrange
        dumped = "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"

        # Act
        loaded = UidJsonField()._deserialize(dumped, None, None)

        # Assert
        assert loaded == UID(dumped)

    def test_code_serialize(self):
        # Arrange
        code = Code("value", "scheme", "meaning")

        # Act
        dumped = CodeJsonField()._serialize(code, None, None)

        # Assert
        assert isinstance(dumped, dict)
        assert_dict_equals_code(dumped, code)

    def test_code_deserialize(self):
        # Arrange
        dumped = {"value": "value", "scheme_designator": "scheme", "meaning": "meaning"}

        # Act
        loaded = CodeJsonField()._deserialize(dumped, None, None)

        # Assert
        assert isinstance(loaded, Code)
        assert_dict_equals_code(dumped, loaded)

    @pytest.mark.parametrize("value", ["value", Code("value", "scheme", "meaning")])
    def test_string_or_code_serialize(self, value: Union[str, Code]):
        # Arrange

        # Act
        dumped = StringOrCodeJsonField()._serialize(value, None, None)

        # Assert
        if isinstance(value, str):
            assert dumped == value
        else:
            assert isinstance(dumped, dict)
            assert_dict_equals_code(dumped, value)

    @pytest.mark.parametrize(
        "dumped",
        [
            "value",
            {"value": "value", "scheme_designator": "scheme", "meaning": "meaning"},
        ],
    )
    def test_string_or_code_deserialize(self, dumped: Union[str, Dict[str, str]]):
        # Arrange

        # Act
        loaded = StringOrCodeJsonField()._deserialize(dumped, None, None)

        # Assert
        if isinstance(dumped, str):
            assert loaded == dumped
        else:
            assert isinstance(loaded, Code)
            assert_dict_equals_code(dumped, loaded)

    @pytest.mark.parametrize(
        "value",
        [10.0, IlluminationColorCode("Full Spectrum")],
    )
    def test_float_or_concept_code_serialize(
        self, value: Union[float, IlluminationColorCode]
    ):
        # Arrange
        field = JsonFieldFactory.float_or_concept_code(IlluminationColorCode)

        # Act
        dumped = field()._serialize(value, None, None)

        # Assert
        if isinstance(value, float):
            assert dumped == value
        else:
            assert_dict_equals_code(dumped, value)

    @pytest.mark.parametrize(
        "dumped",
        [
            10.0,
            {
                "value": "414298005",
                "scheme_designator": "SCT",
                "meaning": "Full Spectrum",
            },
        ],
    )
    def test_float_or_concept_code_deserialize(
        self, dumped: Union[float, Dict[str, str]]
    ):
        # Arrange
        field = JsonFieldFactory.float_or_concept_code(IlluminationColorCode)

        # Act
        loaded = field()._deserialize(dumped, None, None)

        # Assert
        if isinstance(dumped, float):
            assert loaded == dumped
        else:
            assert isinstance(loaded, IlluminationColorCode)
            assert_dict_equals_code(dumped, loaded)

    @pytest.mark.parametrize(
        "value",
        ["value", IlluminationColorCode("Full Spectrum")],
    )
    def test_str_or_concept_code_serialize(
        self, value: Union[str, IlluminationColorCode]
    ):
        # Arrange
        field = JsonFieldFactory.str_or_concept_code(IlluminationColorCode)

        # Act
        dumped = field()._serialize(value, None, None)

        # Assert
        if isinstance(value, str):
            assert dumped == value
        else:
            assert_dict_equals_code(dumped, value)

    @pytest.mark.parametrize(
        "dumped",
        [
            "value",
            {
                "value": "414298005",
                "scheme_designator": "SCT",
                "meaning": "Full Spectrum",
            },
        ],
    )
    def test_str_or_concept_code_deserialize(self, dumped: Union[str, Dict[str, str]]):
        # Arrange
        field = JsonFieldFactory.str_or_concept_code(IlluminationColorCode)

        # Act
        loaded = field()._deserialize(dumped, None, None)

        # Assert
        if isinstance(dumped, str):
            assert loaded == dumped
        else:
            assert isinstance(loaded, IlluminationColorCode)
            assert_dict_equals_code(dumped, loaded)

    def test_concept_code_serialize(self):
        # Arrange
        value = IlluminationColorCode("Full Spectrum")
        field = JsonFieldFactory.concept_code(IlluminationColorCode)

        # Act
        dumped = field()._serialize(value, None, None)

        # Assert
        assert_dict_equals_code(dumped, value)

    def test_concept_code_deserialize(self):
        # Arrange
        dumped = {
            "value": "414298005",
            "scheme_designator": "SCT",
            "meaning": "Full Spectrum",
        }
        field = JsonFieldFactory.concept_code(IlluminationColorCode)

        # Act
        loaded = field()._deserialize(dumped, None, None)

        # Assert
        assert isinstance(loaded, IlluminationColorCode)
        assert_dict_equals_code(dumped, loaded)
