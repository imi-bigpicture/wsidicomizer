import datetime
from typing import Dict, Optional, Union

import pytest
from pydicom.uid import UID
from wsidicom.conceptcode import (
    Code,
    IlluminationCode,
    IlluminationColorCode,
    ImagePathFilterCode,
    LenseCode,
    LightPathFilterCode,
)
from wsidicom.geometry import PointMm

from wsidicomizer.metadata import (
    Equipment,
    ExtendedDepthOfField,
    FocusMethod,
    Image,
    ImageCoordinateSystem,
    ImagePathFilter,
    Label,
    LightPathFilter,
    Objectives,
    OpticalPath,
    Patient,
    PatientDeIdentification,
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
    def test_equipment_serialize(self):
        # Arrange
        equipment = Equipment(
            "manufacturer",
            "model name",
            "device serial number",
            ["software versions 1", "software versions 2"],
        )

        # Act
        dumped = EquipmentSchema().dump(equipment)

        # Assert
        assert isinstance(dumped, dict)
        assert dumped["manufacturer"] == equipment.manufacturer
        assert dumped["model_name"] == equipment.model_name
        assert dumped["device_serial_number"] == equipment.device_serial_number
        assert dumped["software_versions"] == equipment.software_versions

    def test_equipment_deserialize(self):
        # Arrange
        dumped = {
            "manufacturer": "manufacturer",
            "model_name": "model name",
            "device_serial_number": "device serial number",
            "software_versions": ["software versions 1", "software versions 2"],
        }

        # Act
        loaded = EquipmentSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Equipment)
        assert loaded.manufacturer == dumped["manufacturer"]
        assert loaded.model_name == dumped["model_name"]
        assert loaded.device_serial_number == dumped["device_serial_number"]
        assert loaded.software_versions == dumped["software_versions"]

    def test_image_serialize(self):
        # Arrange
        extended_depth_of_field = ExtendedDepthOfField(5, 0.5)
        image_coordinate_system = ImageCoordinateSystem(PointMm(20.0, 30.0), 90.0)
        image = Image(
            datetime.datetime(2023, 8, 5),
            FocusMethod.AUTO,
            extended_depth_of_field,
            image_coordinate_system,
        )

        # Act
        dumped = ImageSchema().dump(image)

        # Assert
        assert image.acquisition_datetime is not None
        assert image.focus_method is not None
        assert isinstance(dumped, dict)
        assert dumped["acquisition_datetime"] == image.acquisition_datetime.isoformat()
        assert dumped["focus_method"] == image.focus_method.value
        assert (
            dumped["extended_depth_of_field"]["number_of_focal_planes"]
            == extended_depth_of_field.number_of_focal_planes
        )
        assert (
            dumped["extended_depth_of_field"]["distance_between_focal_planes"]
            == extended_depth_of_field.distance_between_focal_planes
        )
        assert (
            dumped["image_coordinate_system"]["origin"]["x"]
            == image_coordinate_system.origin.x
        )
        assert (
            dumped["image_coordinate_system"]["origin"]["y"]
            == image_coordinate_system.origin.y
        )
        assert (
            dumped["image_coordinate_system"]["rotation"]
            == image_coordinate_system.rotation
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
        assert loaded.acquisition_datetime == datetime.datetime.fromisoformat(
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

    def test_label_serialize(self):
        # Arrange
        label = Label("label_text", "barcode_value", True, True, False)

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

    @pytest.mark.parametrize(
        "illumination", [IlluminationColorCode("Full Spectrum"), 400.0]
    )
    def test_optical_path_serialize(
        self, illumination: Union[IlluminationColorCode, float]
    ):
        # Arrange
        light_path_filter = LightPathFilter(
            [
                LightPathFilterCode("Green optical filter"),
            ],
            500,
            400,
            600,
        )

        image_path_filter = ImagePathFilter(
            [
                ImagePathFilterCode("Red optical filter"),
            ],
            500,
            400,
            600,
        )

        objective = Objectives(
            [LenseCode("High power non-immersion lens")], 10.0, 20.0, 0.5
        )
        optical_path = OpticalPath(
            "identifier",
            "description",
            IlluminationCode("Brightfield illumination"),
            illumination,
            None,
            None,
            light_path_filter,
            image_path_filter,
            objective,
        )

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
        assert (
            dumped["illumination_type"]["value"] == optical_path.illumination_type.value
        )
        assert (
            dumped["illumination_type"]["scheme_designator"]
            == optical_path.illumination_type.scheme_designator
        )
        assert (
            dumped["illumination_type"]["meaning"]
            == optical_path.illumination_type.meaning
        )
        if isinstance(optical_path.illumination, IlluminationColorCode):
            assert dumped["illumination"]["value"] == optical_path.illumination.value
            assert (
                dumped["illumination"]["scheme_designator"]
                == optical_path.illumination.scheme_designator
            )
            assert (
                dumped["illumination"]["meaning"] == optical_path.illumination.meaning
            )
        else:
            assert dumped["illumination"] == optical_path.illumination
        assert (
            dumped["light_path_filter"]["filters"][0]["value"]
            == optical_path.light_path_filter.filters[0].value
        )
        assert (
            dumped["light_path_filter"]["filters"][0]["meaning"]
            == optical_path.light_path_filter.filters[0].meaning
        )
        assert (
            dumped["light_path_filter"]["filters"][0]["scheme_designator"]
            == optical_path.light_path_filter.filters[0].scheme_designator
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
        assert (
            dumped["image_path_filter"]["filters"][0]["value"]
            == optical_path.image_path_filter.filters[0].value
        )
        assert (
            dumped["image_path_filter"]["filters"][0]["meaning"]
            == optical_path.image_path_filter.filters[0].meaning
        )
        assert (
            dumped["image_path_filter"]["filters"][0]["scheme_designator"]
            == optical_path.image_path_filter.filters[0].scheme_designator
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
        assert (
            dumped["objective"]["lenses"][0]["value"]
            == optical_path.objective.lenses[0].value
        )
        assert (
            dumped["objective"]["lenses"][0]["meaning"]
            == optical_path.objective.lenses[0].meaning
        )
        assert (
            dumped["objective"]["lenses"][0]["scheme_designator"]
            == optical_path.objective.lenses[0].scheme_designator
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
            dumped["objective"]["objective_na"] == optical_path.objective.objective_na
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
                "objective_na": 0.5,
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
        assert loaded.illumination_type.value == dumped["illumination_type"]["value"]
        assert (
            loaded.illumination_type.scheme_designator
            == dumped["illumination_type"]["scheme_designator"]
        )
        assert (
            loaded.illumination_type.meaning == dumped["illumination_type"]["meaning"]
        )
        if isinstance(dumped["illumination"], dict):
            assert isinstance(loaded.illumination, IlluminationColorCode)
            assert loaded.illumination.value == dumped["illumination"]["value"]
            assert (
                loaded.illumination.scheme_designator
                == dumped["illumination"]["scheme_designator"]
            )
            assert loaded.illumination.meaning == dumped["illumination"]["meaning"]
        else:
            assert loaded.illumination == dumped["illumination"]
        assert (
            loaded.light_path_filter.filters[0].value
            == dumped["light_path_filter"]["filters"][0]["value"]
        )
        assert (
            loaded.light_path_filter.filters[0].scheme_designator
            == dumped["light_path_filter"]["filters"][0]["scheme_designator"]
        )
        assert (
            loaded.light_path_filter.filters[0].meaning
            == dumped["light_path_filter"]["filters"][0]["meaning"]
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
        assert (
            loaded.image_path_filter.filters[0].value
            == dumped["image_path_filter"]["filters"][0]["value"]
        )
        assert (
            loaded.image_path_filter.filters[0].scheme_designator
            == dumped["image_path_filter"]["filters"][0]["scheme_designator"]
        )
        assert (
            loaded.image_path_filter.filters[0].meaning
            == dumped["image_path_filter"]["filters"][0]["meaning"]
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

        assert (
            loaded.objective.lenses[0].value
            == dumped["objective"]["lenses"][0]["value"]
        )
        assert (
            loaded.objective.lenses[0].scheme_designator
            == dumped["objective"]["lenses"][0]["scheme_designator"]
        )
        assert (
            loaded.objective.lenses[0].meaning
            == dumped["objective"]["lenses"][0]["meaning"]
        )
        assert (
            loaded.objective.condenser_power == dumped["objective"]["condenser_power"]
        )
        assert (
            loaded.objective.objective_power == dumped["objective"]["objective_power"]
        )
        assert loaded.objective.objective_na == dumped["objective"]["objective_na"]

    @pytest.mark.parametrize(
        "species_description",
        ["specimen description", Code("value", "scheme", "meaning")],
    )
    @pytest.mark.parametrize(
        "method",
        ["identity removed", Code("value", "scheme", "meaning")],
    )
    def test_patient_serialize(
        self,
        species_description: Union[str, Code],
        method: Union[str, Code],
    ):
        # Arrange
        patient_deidentification = PatientDeIdentification(True, [method])
        patient = Patient(
            "name",
            "identifier",
            datetime.datetime(2023, 8, 5),
            PatientSex.O,
            species_description,
            patient_deidentification,
        )

        # Act
        dumped = PatientSchema().dump(patient)

        # Assert
        assert patient.birth_date is not None
        assert patient.sex is not None
        assert patient.de_identification is not None
        assert isinstance(dumped, dict)
        assert dumped["name"] == patient.name
        assert dumped["identifier"] == patient.identifier
        assert dumped["birth_date"] == datetime.date.isoformat(patient.birth_date)
        assert dumped["sex"] == patient.sex.value
        if isinstance(patient.species_description, Code):
            assert isinstance(patient.species_description, Code)
            assert (
                dumped["species_description"]["value"]
                == patient.species_description.value
            )
            assert (
                dumped["species_description"]["scheme_designator"]
                == patient.species_description.scheme_designator
            )
            assert (
                dumped["species_description"]["meaning"]
                == patient.species_description.meaning
            )
        else:
            assert dumped["species_description"] == patient.species_description

        assert (
            dumped["de_identification"]["identity_removed"]
            == patient.de_identification.identity_removed
        )
        if isinstance(method, Code):
            assert patient_deidentification.methods is not None
            assert dumped["de_identification"]["methods"][0]["value"] == method.value
            assert (
                dumped["de_identification"]["methods"][0]["scheme_designator"]
                == method.scheme_designator
            )
            assert (
                dumped["de_identification"]["methods"][0]["meaning"] == method.meaning
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
        assert loaded.birth_date == datetime.date.fromisoformat(dumped["birth_date"])
        assert loaded.sex == PatientSex(dumped["sex"])
        assert loaded.species_description is not None
        if isinstance(species_description, dict):
            assert isinstance(loaded.species_description, Code)
            assert loaded.species_description.value == species_description["value"]
            assert (
                loaded.species_description.scheme_designator
                == species_description["scheme_designator"]
            )
            assert loaded.species_description.meaning == species_description["meaning"]
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

            assert loaded.de_identification.methods[0].value == method["value"]
            assert (
                loaded.de_identification.methods[0].scheme_designator
                == method["scheme_designator"]
            )
            assert loaded.de_identification.methods[0].meaning == method["meaning"]
        else:
            assert loaded.de_identification.methods[0] == method
        assert loaded.de_identification is not None

    def test_series_serialize(self):
        # Arrange
        series = Series(
            UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"), 1
        )

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

    def test_study_serialize(self):
        # Arrange
        study = Study(
            UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"),
            "identifier",
            datetime.date(2023, 8, 5),
            datetime.time(12, 3),
            "accession number",
            "referring physician name",
        )

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
        assert loaded.date == datetime.date.fromisoformat(dumped["date"])
        assert loaded.time == datetime.time.fromisoformat(dumped["time"])
        assert loaded.accession_number == dumped["accession_number"]
        assert loaded.referring_physician_name == dumped["referring_physician_name"]
