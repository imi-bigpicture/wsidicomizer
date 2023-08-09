from datetime import date, time, datetime
from typing import List, Optional, Type, Union

import pytest
from pydicom import Dataset
from pydicom.sr.coding import Code
from pydicom.uid import UID
from wsidicom.conceptcode import ContainerComponentTypeCode
from tests.metadata.helpers import bool_to_dicom_literal
from wsidicomizer.metadata.dicom_attribute import (
    DicomBoolAttribute,
    DicomCodeAttribute,
    DicomDateTimeAttribute,
    DicomListStringAttribute,
    DicomNumericAttribute,
    DicomNumericAttributeType,
    DicomSequenceAttribute,
    DicomStringAttribute,
)


class TestDicomAttribute:
    @pytest.mark.parametrize("required", [True, False])
    @pytest.mark.parametrize("has_value", [True, False])
    @pytest.mark.parametrize("has_default", [True, False])
    def test_dicom_string_attribute(
        self,
        required: bool,
        has_value: bool,
        has_default: bool,
    ):
        # Arrange
        tag = "PatientID"
        value = None
        default = None
        if has_value:
            value = "Patient ID"
        if has_default:
            default = "Default patient ID"
        attribute = DicomStringAttribute(tag, required, value, default)
        dataset = Dataset()

        # Act
        attribute.insert_into_dataset(dataset)

        # Assert
        if required or has_value:
            assert hasattr(dataset, tag)
            dicom_attribute = getattr(dataset, tag)
            if value is not None:
                assert dicom_attribute == value
            elif default is not None:
                assert dicom_attribute == default
            else:
                assert dicom_attribute is None
        else:
            assert not hasattr(dataset, tag)

    @pytest.mark.parametrize("required", [True, False])
    @pytest.mark.parametrize("has_value", [True, False])
    @pytest.mark.parametrize("has_default", [True, False])
    def test_dicom_list_string_attribute(
        self,
        required: bool,
        has_value: bool,
        has_default: bool,
    ):
        # Arrange
        tag = "DeidentificationMethod"
        value = None
        default = None
        if has_value:
            value = ["method 1", "method 2"]
        if has_default:
            default = ["default method 1", "default method 2"]
        attribute = DicomListStringAttribute(tag, required, value, default)
        dataset = Dataset()

        # Act
        attribute.insert_into_dataset(dataset)

        # Assert
        if required or has_value:
            assert hasattr(dataset, tag)
            dicom_attribute = getattr(dataset, tag)
            if value is not None:
                assert dicom_attribute == value
            elif default is not None:
                assert dicom_attribute == default
            else:
                assert len(dicom_attribute) == 0
        else:
            assert not hasattr(dataset, tag)

    @pytest.mark.parametrize("required", [True, False])
    @pytest.mark.parametrize("has_value", [True, False])
    @pytest.mark.parametrize("has_default", [True, False])
    def test_dicom_bool_attribute(
        self,
        required: bool,
        has_value: bool,
        has_default: bool,
    ):
        # Arrange
        tag = "PatientIdentityRemoved"
        value = None
        default = None
        if has_value:
            value = True
        if has_default:
            default = False
        attribute = DicomBoolAttribute(tag, required, value, default)
        dataset = Dataset()

        # Act
        attribute.insert_into_dataset(dataset)

        # Assert
        if required or has_value:
            assert hasattr(dataset, tag)
            dicom_attribute = getattr(dataset, tag)
            if value is not None:
                bool_value = bool_to_dicom_literal(value)
                if value:
                    assert dicom_attribute == bool_value
                else:
                    assert dicom_attribute == bool_value
            elif default is not None:
                bool_value = bool_to_dicom_literal(default)
                if default:
                    assert dicom_attribute == bool_value
                else:
                    assert dicom_attribute == bool_value
            else:
                assert dicom_attribute is None
        else:
            assert not hasattr(dataset, tag)

    @pytest.mark.parametrize("required", [True, False])
    @pytest.mark.parametrize("has_value", [True, False])
    @pytest.mark.parametrize("has_default", [True, False])
    @pytest.mark.parametrize("datetime_type", [datetime, date, time])
    def test_dicom_datetime_attribute(
        self,
        required: bool,
        has_value: bool,
        has_default: bool,
        datetime_type: Union[Type[datetime], Type[date], Type[time]],
    ):
        # Arrange
        if datetime_type == datetime:
            tag = "AcquisitionDateTime"
        elif datetime_type == date:
            tag = "AcquisitionDate"
        else:
            tag = "AcquisitionTime"
        value = None
        default = None
        if has_value:
            if datetime_type == datetime:
                value = datetime(2023, 8, 5, 19, 10, 20)
            elif datetime_type == date:
                value = date(2023, 8, 5)
            else:
                value = time(19, 10, 20)
        if has_default:
            if datetime_type == datetime:
                default = datetime(2023, 8, 6, 20, 10, 20)
            elif datetime_type == date:
                default = date(2023, 8, 6)
            else:
                default = time(20, 10, 20)
        attribute = DicomDateTimeAttribute(tag, required, value, default)
        dataset = Dataset()

        # Act
        attribute.insert_into_dataset(dataset)

        # Assert
        if required or has_value:
            assert hasattr(dataset, tag)
            dicom_attribute = getattr(dataset, tag)
            if value is not None:
                assert dicom_attribute == value
            elif default is not None:
                assert dicom_attribute == default
            else:
                assert dicom_attribute is None
        else:
            assert not hasattr(dataset, tag)

    @pytest.mark.parametrize("required", [True, False])
    @pytest.mark.parametrize("has_value", [True, False])
    @pytest.mark.parametrize("has_default", [True, False])
    def test_dicom_code_attribute(
        self,
        required: bool,
        has_value: bool,
        has_default: bool,
    ):
        # Arrange
        tag = "SpecimenTypeCodeSequence"
        value = None
        default = None
        if has_value:
            value = Code("value", "scheme", "meaning")
        if has_default:
            default = Code("default value", "default scheme", "default meaning")
        attribute = DicomCodeAttribute(tag, required, value, default)
        dataset = Dataset()

        # Act
        attribute.insert_into_dataset(dataset)

        # Assert
        if required or has_value:
            assert hasattr(dataset, tag)
            dicom_attribute = getattr(dataset, tag)
            if value is not None:
                assert dicom_attribute[0].CodeValue == value.value
                assert (
                    dicom_attribute[0].CodingSchemeDesignator == value.scheme_designator
                )
                assert dicom_attribute[0].CodeMeaning == value.meaning
            elif default is not None:
                assert dicom_attribute[0].CodeValue == default.value
                assert (
                    dicom_attribute[0].CodingSchemeDesignator
                    == default.scheme_designator
                )
                assert dicom_attribute[0].CodeMeaning == default.meaning
            else:
                assert len(dicom_attribute) == 0
        else:
            assert not hasattr(dataset, tag)

    @pytest.mark.parametrize("required", [True, False])
    @pytest.mark.parametrize("has_value", [True, False])
    @pytest.mark.parametrize("has_default", [True, False])
    def test_dicom_uid_attribute(
        self,
        required: bool,
        has_value: bool,
        has_default: bool,
    ):
        # Arrange
        tag = "StudyInstanceUID"
        value = None
        default = None
        if has_value:
            value = UID(
                "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"
            )
        if has_default:
            default = UID(
                "1.2.826.0.1.3680043.8.498.10383123073750612403801569759348987394"
            )
        attribute = DicomStringAttribute(tag, required, value, default)
        dataset = Dataset()

        # Act
        attribute.insert_into_dataset(dataset)

        # Assert
        if required or has_value:
            assert hasattr(dataset, tag)
            dicom_attribute = getattr(dataset, tag)
            if value is not None:
                assert dicom_attribute == value
            elif default is not None:
                assert dicom_attribute == default
            else:
                assert dicom_attribute is None
        else:
            assert not hasattr(dataset, tag)

    @pytest.mark.parametrize("required", [True, False])
    @pytest.mark.parametrize("has_value", [True, False])
    @pytest.mark.parametrize("has_default", [True, False])
    @pytest.mark.parametrize(
        "number_type",
        [
            DicomNumericAttributeType.FLOAT_STRING,
            DicomNumericAttributeType.DECIMAL_STRING,
            DicomNumericAttributeType.INTEGER_STRING,
            DicomNumericAttributeType.NOT_STRING,
        ],
    )
    def test_dicom_number_attribute(
        self,
        required: bool,
        has_value: bool,
        has_default: bool,
        number_type: DicomNumericAttributeType,
    ):
        # Arrange
        if number_type == DicomNumericAttributeType.FLOAT_STRING:
            tag = "FloatPixelData"
        elif number_type == DicomNumericAttributeType.DECIMAL_STRING:
            tag = "PatientSize"
        elif number_type == DicomNumericAttributeType.INTEGER_STRING:
            tag = "ImagesInAcquisition"
        else:
            tag = "IlluminationWaveLength"

        value = None
        default = None
        if has_value:
            if number_type == DicomNumericAttributeType.FLOAT_STRING:
                value = 123.4
            elif number_type == DicomNumericAttributeType.DECIMAL_STRING:
                value = 123.4
            elif number_type == DicomNumericAttributeType.INTEGER_STRING:
                value = 123
            else:
                value = 123.4
        if has_default:
            if number_type == DicomNumericAttributeType.FLOAT_STRING:
                default = 432.1
            elif number_type == DicomNumericAttributeType.DECIMAL_STRING:
                default = 432.1
            elif number_type == DicomNumericAttributeType.INTEGER_STRING:
                default = 432
            else:
                default = 432.1
        attribute = DicomNumericAttribute(tag, required, value, default, number_type)
        dataset = Dataset()

        # Act
        attribute.insert_into_dataset(dataset)

        # Assert
        if required or has_value:
            assert hasattr(dataset, tag)
            dicom_attribute = getattr(dataset, tag)
            if value is not None:
                assert dicom_attribute == value
            elif default is not None:
                assert dicom_attribute == default
            else:
                assert dicom_attribute is None
        else:
            assert not hasattr(dataset, tag)

    @pytest.mark.parametrize("required", [True, False])
    @pytest.mark.parametrize("has_value", [True, False])
    @pytest.mark.parametrize("has_default", [True, False])
    def test_dicom_sequence_attribute(
        self,
        required: bool,
        has_value: bool,
        has_default: bool,
    ):
        # Arrange
        tag = "ContainerComponentSequence"
        value = None
        default = None
        if has_value:
            value = [DicomStringAttribute("ContainerComponentMaterial", False, "GLASS")]
        if has_default:
            default = [
                DicomStringAttribute("ContainerComponentMaterial", False, "PLASTIC")
            ]
        attribute = DicomSequenceAttribute(tag, required, value, default)
        dataset = Dataset()

        # Act
        attribute.insert_into_dataset(dataset)

        # Assert
        if required or has_value:
            assert hasattr(dataset, tag)
            dicom_attribute = getattr(dataset, tag)
            if value is not None:
                assert dicom_attribute[0].ContainerComponentMaterial == value[0].value
            elif default is not None:
                assert dicom_attribute[0].ContainerComponentMaterial == default[0].value
            else:
                assert len(dicom_attribute) == 0
        else:
            assert not hasattr(dataset, tag)
