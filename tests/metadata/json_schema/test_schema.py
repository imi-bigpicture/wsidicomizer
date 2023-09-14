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

from datetime import datetime, date, time
from typing import Dict, Optional, Sequence, Union

import pytest
from pydicom.uid import UID
from wsidicom.conceptcode import Code, IlluminationColorCode
from wsidicom.geometry import PointMm
from tests.metadata.helpers import assert_dict_equals_code

from wsidicomizer.metadata import (
    Equipment,
    ExtendedDepthOfField,
    FocusMethod,
    Image,
    ImageCoordinateSystem,
    Label,
    OpticalPath,
    Patient,
    PatientSex,
    Series,
    Study,
)
from wsidicomizer.metadata.schema.equipment import EquipmentSchema
from wsidicomizer.metadata.schema.image import ImageSchema
from wsidicomizer.metadata.schema.label import LabelSchema
from wsidicomizer.metadata.schema.optical import OpticalPathSchema
from wsidicomizer.metadata.schema.patient import PatientSchema
from wsidicomizer.metadata.schema.series import SeriesSchema
from wsidicomizer.metadata.schema.study import StudySchema


class TestSchema:
    @pytest.mark.parametrize(
        ["manufacturer", "model_name", "serial_number", "versions"],
        [
            ["manufacturer", "model_name", "serial_number", ["version"]],
            ["manufacturer", "model_name", "serial_number", ["version 1", "version 2"]],
            [None, None, None, None],
        ],
    )
    def test_equipment_serialize(self, equipment: Equipment):
        # Arrange

        # Act
        dumped = EquipmentSchema().dump(equipment)

        # Assert
        assert isinstance(dumped, dict)
        assert dumped["manufacturer"] == equipment.manufacturer
        assert dumped["model_name"] == equipment.model_name
        assert dumped["device_serial_number"] == equipment.device_serial_number
        assert dumped["software_versions"] == equipment.software_versions

    @pytest.mark.parametrize(
        ["manufacturer", "model_name", "serial_number", "versions"],
        [
            ["manufacturer", "model_name", "serial_number", ["version"]],
            ["manufacturer", "model_name", "serial_number", ["version 1", "version 2"]],
            [None, None, None, None],
        ],
    )
    def test_equipment_deserialize(
        self,
        manufacturer: Optional[str],
        model_name: Optional[str],
        serial_number: Optional[str],
        versions: Optional[Sequence[str]],
    ):
        # Arrange
        dumped = {
            "manufacturer": manufacturer,
            "model_name": model_name,
            "device_serial_number": serial_number,
            "software_versions": versions,
        }

        # Act
        loaded = EquipmentSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Equipment)
        assert loaded.manufacturer == dumped["manufacturer"]
        assert loaded.model_name == dumped["model_name"]
        assert loaded.device_serial_number == dumped["device_serial_number"]
        assert loaded.software_versions == dumped["software_versions"]

    @pytest.mark.parametrize(
        [
            "acquisition_datetime",
            "focus_method",
            "extended_depth_of_field",
            "image_coordinate_system",
        ],
        [
            [
                datetime(2023, 8, 5),
                FocusMethod.AUTO,
                ExtendedDepthOfField(5, 0.5),
                ImageCoordinateSystem(PointMm(20.0, 30.0), 90.0),
            ],
            [
                datetime(2023, 8, 5, 12, 13, 14, 150),
                FocusMethod.MANUAL,
                ExtendedDepthOfField(15, 0.5),
                ImageCoordinateSystem(PointMm(50.0, 20.0), 180.0),
            ],
            [None, None, None, None],
        ],
    )
    def test_image_serialize(self, image: Image):
        # Arrange

        # Act
        dumped = ImageSchema().dump(image)

        # Assert

        assert isinstance(dumped, dict)
        if image.acquisition_datetime is None:
            assert dumped["acquisition_datetime"] == None
        else:
            assert (
                dumped["acquisition_datetime"] == image.acquisition_datetime.isoformat()
            )
        if image.focus_method is None:
            assert dumped["focus_method"] == None
        else:
            assert dumped["focus_method"] == image.focus_method.value
        if image.extended_depth_of_field is None:
            assert dumped["extended_depth_of_field"] == None
        else:
            assert (
                dumped["extended_depth_of_field"]["number_of_focal_planes"]
                == image.extended_depth_of_field.number_of_focal_planes
            )
            assert (
                dumped["extended_depth_of_field"]["distance_between_focal_planes"]
                == image.extended_depth_of_field.distance_between_focal_planes
            )
        if image.image_coordinate_system is None:
            assert dumped["image_coordinate_system"] == None
        else:
            assert (
                dumped["image_coordinate_system"]["origin"]["x"]
                == image.image_coordinate_system.origin.x
            )
            assert (
                dumped["image_coordinate_system"]["origin"]["y"]
                == image.image_coordinate_system.origin.y
            )
            assert (
                dumped["image_coordinate_system"]["rotation"]
                == image.image_coordinate_system.rotation
            )

    def test_image_deserialize(self):
        # Arrange
        dumped = {
            "acquisition_datetime": "2023-08-05T00:00:00",
            "focus_method": "auto",
            "extended_depth_of_field": {
                "number_of_focal_planes": 5,
                "distance_between_focal_planes": 0.5,
            },
            "image_coordinate_system": {
                "origin": {"x": 20.0, "y": 30.0},
                "rotation": 90.0,
            },
        }

        # Act
        loaded = ImageSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Image)
        assert loaded.extended_depth_of_field is not None
        assert loaded.image_coordinate_system is not None
        assert loaded.acquisition_datetime == datetime.fromisoformat(
            dumped["acquisition_datetime"]
        )
        assert loaded.focus_method == FocusMethod(dumped["focus_method"])
        assert (
            loaded.extended_depth_of_field.number_of_focal_planes
            == dumped["extended_depth_of_field"]["number_of_focal_planes"]
        )
        assert (
            loaded.extended_depth_of_field.distance_between_focal_planes
            == dumped["extended_depth_of_field"]["distance_between_focal_planes"]
        )
        assert (
            loaded.image_coordinate_system.origin.x
            == dumped["image_coordinate_system"]["origin"]["x"]
        )
        assert (
            loaded.image_coordinate_system.origin.y
            == dumped["image_coordinate_system"]["origin"]["y"]
        )
        assert (
            loaded.image_coordinate_system.rotation
            == dumped["image_coordinate_system"]["rotation"]
        )

    def test_label_serialize(self, label: Label):
        # Arrange

        # Act
        dumped = LabelSchema().dump(label)

        # Assert
        assert isinstance(dumped, dict)
        assert dumped["label_text"] == label.label_text
        assert dumped["barcode_value"] == label.barcode_value
        assert dumped["label_in_volume_image"] == label.label_in_volume_image
        assert dumped["label_in_overview_image"] == label.label_in_overview_image
        assert dumped["label_is_phi"] == label.label_is_phi

    def test_label_deserialize(self):
        # Arrange
        dumped = {
            "label_text": "label_text",
            "barcode_value": "barcode_value",
            "label_in_volume_image": True,
            "label_in_overview_image": True,
            "label_is_phi": False,
        }

        # Act
        loaded = LabelSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Label)
        assert loaded.label_text == dumped["label_text"]
        assert loaded.barcode_value == dumped["barcode_value"]
        assert loaded.label_in_volume_image == dumped["label_in_volume_image"]
        assert loaded.label_in_overview_image == dumped["label_in_overview_image"]
        assert loaded.label_is_phi == dumped["label_is_phi"]

    def test_optical_path_serialize(self, optical_path: OpticalPath):
        # Arrange

        # Act
        dumped = OpticalPathSchema().dump(optical_path)

        # Assert
        assert isinstance(dumped, dict)
        assert optical_path.illumination_type is not None
        assert optical_path.light_path_filter is not None
        assert optical_path.image_path_filter is not None
        assert optical_path.objective is not None
        assert dumped["identifier"] == optical_path.identifier
        assert dumped["description"] == optical_path.description
        assert_dict_equals_code(
            dumped["illumination_type"], optical_path.illumination_type
        )

        if isinstance(optical_path.illumination, IlluminationColorCode):
            assert_dict_equals_code(dumped["illumination"], optical_path.illumination)
        else:
            assert dumped["illumination"] == optical_path.illumination
        assert_dict_equals_code(
            dumped["light_path_filter"]["filters"][0],
            optical_path.light_path_filter.filters[0],
        )
        assert (
            dumped["light_path_filter"]["nominal"]
            == optical_path.light_path_filter.nominal
        )
        assert (
            dumped["light_path_filter"]["low_pass"]
            == optical_path.light_path_filter.low_pass
        )
        assert (
            dumped["light_path_filter"]["high_pass"]
            == optical_path.light_path_filter.high_pass
        )
        assert_dict_equals_code(
            dumped["image_path_filter"]["filters"][0],
            optical_path.image_path_filter.filters[0],
        )
        assert (
            dumped["image_path_filter"]["nominal"]
            == optical_path.image_path_filter.nominal
        )
        assert (
            dumped["image_path_filter"]["low_pass"]
            == optical_path.image_path_filter.low_pass
        )
        assert (
            dumped["image_path_filter"]["high_pass"]
            == optical_path.image_path_filter.high_pass
        )
        assert_dict_equals_code(
            dumped["objective"]["lenses"][0],
            optical_path.objective.lenses[0],
        )
        assert (
            dumped["objective"]["condenser_power"]
            == optical_path.objective.condenser_power
        )
        assert (
            dumped["objective"]["objective_power"]
            == optical_path.objective.objective_power
        )
        assert (
            dumped["objective"]["objective_numerical_aperature"]
            == optical_path.objective.objective_numerical_aperature
        )

    @pytest.mark.parametrize(
        "illumination",
        [
            {
                "value": "414298005",
                "scheme_designator": "SCT",
                "meaning": "Full Spectrum",
            },
            400.0,
        ],
    )
    def test_optical_path_deserialize(self, illumination: Union[Dict[str, str], float]):
        dumped = {
            "identifier": "identifier",
            "description": "description",
            "illumination_type": {
                "value": "111744",
                "scheme_designator": "DCM",
                "meaning": "Brightfield illumination",
            },
            "light_path_filter": {
                "filters": [
                    {
                        "value": "445465004",
                        "scheme_designator": "SCT",
                        "meaning": "Green optical filter",
                    }
                ],
                "nominal": 500.0,
                "low_pass": 400.0,
                "high_pass": 600.0,
            },
            "image_path_filter": {
                "filters": [
                    {
                        "value": "445279009",
                        "scheme_designator": "SCT",
                        "meaning": "Red optical filter",
                    }
                ],
                "nominal": 500.0,
                "low_pass": 400.0,
                "high_pass": 600.0,
            },
            "objective": {
                "lenses": [
                    {
                        "value": "445621001",
                        "scheme_designator": "SCT",
                        "meaning": "High power non-immersion lens",
                    }
                ],
                "condenser_power": 10.0,
                "objective_power": 20.0,
                "objective_numerical_aperature": 0.5,
            },
        }
        dumped["illumination"] = illumination

        # Act
        loaded = OpticalPathSchema().load(dumped)

        # Assert
        assert isinstance(loaded, OpticalPath)
        assert loaded.illumination_type is not None
        assert loaded.light_path_filter is not None
        assert loaded.image_path_filter is not None
        assert loaded.objective is not None
        assert loaded.identifier == dumped["identifier"]
        assert loaded.description == dumped["description"]
        assert_dict_equals_code(
            dumped["illumination_type"],
            loaded.illumination_type,
        )
        if isinstance(dumped["illumination"], dict):
            assert isinstance(loaded.illumination, IlluminationColorCode)
            assert_dict_equals_code(
                dumped["illumination"],
                loaded.illumination,
            )
        else:
            assert loaded.illumination == dumped["illumination"]
        assert_dict_equals_code(
            dumped["light_path_filter"]["filters"][0],
            loaded.light_path_filter.filters[0],
        )
        assert (
            loaded.light_path_filter.nominal == dumped["light_path_filter"]["nominal"]
        )
        assert (
            loaded.light_path_filter.low_pass == dumped["light_path_filter"]["low_pass"]
        )
        assert (
            loaded.light_path_filter.high_pass
            == dumped["light_path_filter"]["high_pass"]
        )
        assert_dict_equals_code(
            dumped["image_path_filter"]["filters"][0],
            loaded.image_path_filter.filters[0],
        )
        assert (
            loaded.image_path_filter.nominal == dumped["image_path_filter"]["nominal"]
        )
        assert (
            loaded.image_path_filter.low_pass == dumped["image_path_filter"]["low_pass"]
        )
        assert (
            loaded.image_path_filter.high_pass
            == dumped["image_path_filter"]["high_pass"]
        )
        assert_dict_equals_code(
            dumped["objective"]["lenses"][0],
            loaded.objective.lenses[0],
        )
        assert (
            loaded.objective.condenser_power == dumped["objective"]["condenser_power"]
        )
        assert (
            loaded.objective.objective_power == dumped["objective"]["objective_power"]
        )
        assert (
            loaded.objective.objective_numerical_aperature
            == dumped["objective"]["objective_numerical_aperature"]
        )

    def test_patient_serialize(self, patient: Patient):
        # Arrange

        # Act
        dumped = PatientSchema().dump(patient)

        # Assert
        assert patient.birth_date is not None
        assert patient.sex is not None
        assert patient.de_identification is not None
        assert patient.de_identification.methods is not None
        assert isinstance(dumped, dict)
        assert dumped["name"] == patient.name
        assert dumped["identifier"] == patient.identifier
        assert dumped["birth_date"] == date.isoformat(patient.birth_date)
        assert dumped["sex"] == patient.sex.value
        if isinstance(patient.species_description, Code):
            assert isinstance(patient.species_description, Code)
            assert_dict_equals_code(
                dumped["species_description"],
                patient.species_description,
            )
        else:
            assert dumped["species_description"] == patient.species_description

        assert (
            dumped["de_identification"]["identity_removed"]
            == patient.de_identification.identity_removed
        )
        method = patient.de_identification.methods[0]
        if isinstance(method, Code):
            assert_dict_equals_code(
                dumped["de_identification"]["methods"][0],
                method,
            )
        else:
            assert dumped["de_identification"]["methods"][0] == method

    @pytest.mark.parametrize(
        "species_description",
        [
            "specimen description",
            {
                "value": "value",
                "scheme_designator": "scheme",
                "meaning": "meaning",
            },
        ],
    )
    @pytest.mark.parametrize(
        "method",
        [
            "identity removed",
            {
                "value": "value",
                "scheme_designator": "scheme",
                "meaning": "meaning",
            },
        ],
    )
    def test_patient_deidentification(
        self,
        species_description: Union[str, Dict[str, str]],
        method: Union[str, Dict[str, str]],
    ):
        # Arrange
        dumped = {
            "name": "name",
            "identifier": "identifier",
            "birth_date": "2023-08-05",
            "sex": "other",
            "de_identification": {
                "identity_removed": True,
            },
        }
        dumped["species_description"] = species_description
        dumped["de_identification"]["methods"] = [method]

        # Act
        loaded = PatientSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Patient)
        assert loaded.name == dumped["name"]
        assert loaded.identifier == dumped["identifier"]
        assert loaded.birth_date == date.fromisoformat(dumped["birth_date"])
        assert loaded.sex == PatientSex(dumped["sex"])
        assert loaded.species_description is not None
        if isinstance(species_description, dict):
            assert isinstance(loaded.species_description, Code)
            assert_dict_equals_code(
                species_description,
                loaded.species_description,
            )
        else:
            assert loaded.species_description == species_description
        assert loaded.de_identification is not None
        assert (
            loaded.de_identification.identity_removed
            == dumped["de_identification"]["identity_removed"]
        )
        assert isinstance(loaded.de_identification.methods, list)
        if isinstance(method, dict):
            assert isinstance(loaded.de_identification.methods[0], Code)
            assert_dict_equals_code(
                method,
                loaded.de_identification.methods[0],
            )
        else:
            assert loaded.de_identification.methods[0] == method
        assert loaded.de_identification is not None

    def test_series_serialize(self, series: Series):
        # Arrange

        # Act
        dumped = SeriesSchema().dump(series)

        # Assert
        assert isinstance(dumped, dict)
        assert dumped["uid"] == str(series.uid)
        assert dumped["number"] == series.number

    def test_series_deserialize(self):
        dumped = {
            "uid": "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423",
            "number": 1,
        }

        # Act
        loaded = SeriesSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Series)
        assert loaded.uid == UID(dumped["uid"])
        assert loaded.number == dumped["number"]

    def test_study_serialize(self, study: Study):
        # Arrange

        # Act
        dumped = StudySchema().dump(study)

        # Assert
        assert study.date is not None
        assert study.time is not None
        assert isinstance(dumped, dict)
        dumped["uid"] = str(study.uid)
        dumped["identifier"] = study.identifier
        dumped["date"] = study.date.isoformat()
        dumped["time"] = study.time.isoformat()
        dumped["accession_number"] = study.accession_number
        dumped["referring_physician_name"] = study.referring_physician_name

    def test_study_deserialize(self):
        # Arrange
        dumped = {
            "uid": "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423",
            "identifier": "identifier",
            "date": "2023-08-05",
            "time": "12:03:00",
            "accession_number": "accession number",
            "referring_physician_name": "referring physician name",
        }

        # Act
        loaded = StudySchema().load(dumped)

        # Assert
        assert isinstance(loaded, Study)
        assert loaded.uid == UID(dumped["uid"])
        assert loaded.identifier == dumped["identifier"]
        assert loaded.date == date.fromisoformat(dumped["date"])
        assert loaded.time == time.fromisoformat(dumped["time"])
        assert loaded.accession_number == dumped["accession_number"]
        assert loaded.referring_physician_name == dumped["referring_physician_name"]
