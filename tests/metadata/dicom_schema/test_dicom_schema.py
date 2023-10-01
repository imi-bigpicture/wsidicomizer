from datetime import datetime

import pytest
from pydicom import Dataset
from pydicom.sr.coding import Code
from wsidicom.conceptcode import (
    IlluminationColorCode,
    ImagePathFilterCode,
    LightPathFilterCode,
    LenseCode,
)
from wsidicom.geometry import PointMm
from wsidicom.instance import ImageType

from tests.metadata.helpers import (
    assert_dicom_bool_equals_bool,
    assert_dicom_code_dataset_equals_code,
    assert_dicom_code_sequence_equals_codes,
    bool_to_dicom_literal,
    code_to_code_dataset,
)
from wsidicomizer.metadata import (
    Equipment,
    ExtendedDepthOfField,
    FocusMethod,
    Image,
    ImageCoordinateSystem,
    Label,
    OpticalPath,
    Patient,
    Series,
    Study,
    WsiMetadata,
    Slide,
    ImagePathFilter,
    LightPathFilter,
    Objectives,
)
from wsidicomizer.metadata.defaults import Defaults

from wsidicomizer.metadata.dicom_schema.equipment import EquipmentDicomSchema
from wsidicomizer.metadata.dicom_schema.image import ImageDicomSchema
from wsidicomizer.metadata.dicom_schema.label import LabelDicomSchema
from wsidicomizer.metadata.dicom_schema.optical_path import OpticalPathDicomSchema
from wsidicomizer.metadata.dicom_schema.patient import PatientDicomSchema
from wsidicomizer.metadata.dicom_schema.series import SeriesDicomSchema
from wsidicomizer.metadata.dicom_schema.slide import SlideDicomSchema
from wsidicomizer.metadata.dicom_schema.study import StudyDicomSchema
from wsidicomizer.metadata.dicom_schema.wsi import WsiMetadataDicomSchema


class TestDicomSchema:
    @pytest.mark.parametrize(
        ["manufacturer", "model_name", "serial_number", "versions"],
        [
            ["manufacturer", "model_name", "serial_number", ["version"]],
            ["manufacturer", "model_name", "serial_number", ["version 1", "version 2"]],
        ],
    )
    def test_serialize_eqipment(self, equipment: Equipment):
        # Arrange
        model = EquipmentDicomSchema()
        assert equipment.software_versions is not None

        # Act
        serialized = model.dump(equipment)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_equipment_equals_equipment(serialized, equipment)

    def test_serialize_defaualt_eqipment(self):
        # Arrange
        equipment = Equipment()
        model = EquipmentDicomSchema()

        # Act
        serialized = model.dump(equipment)

        # Assert
        assert isinstance(serialized, Dataset)
        assert serialized.Manufacturer == Defaults.string
        assert serialized.ManufacturerModelName == Defaults.string
        assert serialized.DeviceSerialNumber == Defaults.string
        assert serialized.SoftwareVersions == Defaults.string

    @pytest.mark.parametrize(
        ["manufacturer", "model_name", "serial_number", "versions"],
        [
            ["manufacturer", "model_name", "serial_number", ["version"]],
            ["manufacturer", "model_name", "serial_number", ["version 1", "version 2"]],
            [None, None, None, None],
        ],
    )
    def test_deserialize_dicom_equipment(
        self, dicom_equipment: Dataset, equipment: Equipment
    ):
        # Arrange
        model = EquipmentDicomSchema()

        # Act
        deserialized = model.load(dicom_equipment)

        # Assert
        assert isinstance(deserialized, Equipment)
        assert deserialized == equipment

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
        ],
    )
    def test_serialize_image(self, image: Image):
        # Arrange
        model = ImageDicomSchema()

        # Act
        serialized = model.dump(image)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_image_equals_image(serialized, image)

    def test_serialize_default_image(self):
        # Arrange
        image = Image()
        model = ImageDicomSchema()

        # Act
        serialized = model.dump(image)

        # Assert
        assert isinstance(serialized, Dataset)
        assert serialized.AcquisitionDateTime == Defaults.date_time
        assert serialized.FocusMethod == Defaults.focus_method.name
        assert serialized.ExtendedDepthOfField == "NO"
        print(serialized)

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
    def test_deserialize_image(self, dicom_image: Dataset, image: Image):
        # Arrange
        model = ImageDicomSchema()

        # Act
        deserialized = model.load(dicom_image)
        assert isinstance(deserialized, Image)
        assert deserialized == image

    @pytest.mark.parametrize(
        "image_type", [ImageType.LABEL, ImageType.OVERVIEW, ImageType.VOLUME]
    )
    def test_serialize_label(self, label: Label, image_type: ImageType):
        # Arrange
        schema = LabelDicomSchema(context={"image_type": image_type})

        # Act
        serialized = schema.dump(label)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_label_equals_label(serialized, label, image_type)

    @pytest.mark.parametrize(
        "image_type", [ImageType.LABEL, ImageType.OVERVIEW, ImageType.VOLUME]
    )
    def test_serialize_default_label(self, image_type: ImageType):
        # Arrange
        label = Label()
        schema = LabelDicomSchema(context={"image_type": image_type})

        # Act
        serialized = schema.dump(label)

        # Assert
        assert isinstance(serialized, Dataset)
        if image_type == ImageType.LABEL:
            assert serialized.LabelText == None
            assert serialized.BarcodeValue == None
            assert serialized.SpecimenLabelInImage == "YES"
            assert serialized.BurnedInAnnotation == "YES"
        else:
            assert "LabelText" not in serialized
            assert "BarcodeValue" not in serialized
            assert serialized.SpecimenLabelInImage == "NO"
            assert serialized.BurnedInAnnotation == "NO"

    @pytest.mark.parametrize(
        "image_type", [ImageType.LABEL, ImageType.OVERVIEW, ImageType.VOLUME]
    )
    def test_deserialize_label(
        self, dicom_label: Dataset, label: Label, image_type: ImageType
    ):
        # Arrange
        schema = LabelDicomSchema()

        # Act
        deserialized = schema.load(dicom_label)

        # Assert
        assert isinstance(deserialized, Label)
        if image_type == ImageType.LABEL:
            assert deserialized.text == label.text
            assert deserialized.barcode == label.barcode
            assert deserialized.label_is_phi == label.label_is_phi
        elif image_type == ImageType.VOLUME:
            assert deserialized.text is None
            assert deserialized.barcode is None
            assert deserialized.label_in_volume_image == label.label_in_volume_image
            assert deserialized.label_is_phi == label.label_is_phi
        elif image_type == ImageType.OVERVIEW:
            assert deserialized.text is None
            assert deserialized.barcode is None
            assert deserialized.label_in_overview_image == label.label_in_overview_image
            assert deserialized.label_is_phi == label.label_is_phi

    @pytest.mark.parametrize(
        "illumination", [IlluminationColorCode("Full Spectrum"), 400.0]
    )
    def test_serialize_optical_path(self, optical_path: OpticalPath):
        # Arrange
        schema = OpticalPathDicomSchema()

        # Act
        serialized = schema.dump(optical_path)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_optical_path_equals_optical_path(serialized, optical_path)

    def test_serialize_default_optical_path(self):
        # Arrange
        optical_path = OpticalPath()
        schema = OpticalPathDicomSchema()

        # Act
        serialized = schema.dump(optical_path)

        # Assert
        print(serialized)
        # TODO Assert id is filled
        assert isinstance(serialized, Dataset)
        assert_dicom_code_sequence_equals_codes(
            serialized.IlluminationTypeCodeSequence, [Defaults.illumination_type]
        )
        # TODO empty should not be in serialized
        # assert "OpticalPathDescription" not in serialized
        assert "IlluminationWaveLength" not in serialized
        assert_dicom_code_dataset_equals_code(
            serialized.IlluminationColorCodeSequence[0], Defaults.illumination
        )
        assert "LensesCodeSequence" not in serialized
        assert "CondenserLensPower" not in serialized
        assert "ObjectiveLensPower" not in serialized
        assert "ObjectiveLensNumericalAperture" not in serialized
        assert "LightPathFilterTypeStackCodeSequence" not in serialized
        assert "LightPathFilterPassThroughWavelength" not in serialized
        assert "LightPathFilterPassBand" not in serialized
        assert "ImagePathFilterTypeStackCodeSequence" not in serialized
        assert "ImagePathFilterPassThroughWavelength" not in serialized
        assert "ImagePathFilterPassBand" not in serialized

    @pytest.mark.parametrize(
        "illumination", [IlluminationColorCode("Full Spectrum"), 400.0, None]
    )
    @pytest.mark.parametrize(
        ["light_path_filter", "image_path_filter", "objectives"],
        [
            [
                LightPathFilter(
                    [LightPathFilterCode("Green optical filter")],
                    500,
                    400,
                    600,
                ),
                ImagePathFilter(
                    [ImagePathFilterCode("Red optical filter")],
                    500,
                    400,
                    600,
                ),
                Objectives(
                    [LenseCode("High power non-immersion lens")], 10.0, 20.0, 0.5
                ),
            ],
            [None, None, None],
        ],
    )
    def test_deserialize_optical_path(
        self, dicom_optical_path: Dataset, optical_path: OpticalPath
    ):
        # Arrange
        schema = OpticalPathDicomSchema()

        # Act
        deserialized = schema.load(dicom_optical_path)

        # Assert
        assert deserialized == optical_path

    def test_serialize_patient(self, patient: Patient):
        # Arrange
        schema = PatientDicomSchema()

        # Act
        serialized = schema.dump(patient)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_patient_equals_patient(serialized, patient)

    def test_serialize_default_patient(self):
        # Arrange
        patient = Patient()
        schema = PatientDicomSchema()

        # Act
        serialized = schema.dump(patient)
        assert isinstance(serialized, Dataset)
        assert serialized.PatientName == None
        assert serialized.PatientID == None
        assert serialized.PatientBirthDate == None
        assert serialized.PatientSex == None
        assert "PatientSpeciesDescription" not in serialized
        assert "PatientSpeciesCodeSequence" not in serialized
        assert "PatientIdentityRemoved" not in serialized
        assert "DeidentificationMethod" not in serialized
        assert "DeidentificationMethodCodeSequence" not in serialized

    def test_deserialize_patient(self, dicom_patient: Dataset, patient: Patient):
        # Arrange

        schema = PatientDicomSchema()

        # Act
        deserialized = schema.load(dicom_patient)

        # Assert
        assert isinstance(deserialized, Patient)
        assert deserialized == patient

    def test_serialize_series(self, series: Series):
        # Arrange
        schema = SeriesDicomSchema()

        # Act
        serialized = schema.dump(series)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_series_equals_series(serialized, series)

    def test_serialize_default_series(self):
        # Arrange
        series = Series()
        schema = SeriesDicomSchema()

        # Act
        serialized = schema.dump(series)

        # Assert
        assert isinstance(serialized, Dataset)
        assert serialized.SeriesInstanceUID == series._uid
        assert serialized.SeriesNumber == 1

    def test_deserialize_series(self, dicom_series: Dataset, series: Series):
        # Arrange

        schema = SeriesDicomSchema()

        # Act
        deserialized = schema.load(dicom_series)

        # Assert
        assert isinstance(deserialized, Series)
        assert deserialized == series

    def test_serialize_study(self, study: Study):
        # Arrange
        schema = StudyDicomSchema()

        # Act
        serialized = schema.dump(study)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_study_equals_study(serialized, study)

    def test_serialize_default_study(self):
        # Arrange
        study = Study()
        schema = StudyDicomSchema()

        # Act
        serialized = schema.dump(study)

        # Assert
        assert isinstance(serialized, Dataset)
        assert serialized.StudyInstanceUID == study._uid
        assert serialized.StudyID == None
        assert serialized.StudyDate == None
        assert serialized.StudyTime == None
        assert serialized.AccessionNumber == None
        assert serialized.ReferringPhysicianName == None

    def test_deserialize_study(self, dicom_study: Dataset, study: Study):
        # Arrange
        schema = StudyDicomSchema()

        # Act
        deserialized = schema.load(dicom_study)

        # Assert
        assert isinstance(deserialized, Study)
        assert deserialized == study

    def test_serialize_slide(self, slide: Slide):
        # Arrange
        schema = SlideDicomSchema()

        # Act
        serialized = schema.dump(slide)

        # Assert
        assert isinstance(serialized, Dataset)
        assert serialized.ContainerIdentifier == slide.identifier
        assert_dicom_code_dataset_equals_code(
            serialized.ContainerTypeCodeSequence[0], Defaults.slide_container_type
        )
        if slide.samples is not None:
            assert len(serialized.SpecimenDescriptionSequence) == len(slide.samples)
            for specimen_description, sample in zip(
                serialized.SpecimenDescriptionSequence, slide.samples
            ):
                assert specimen_description.SpecimenIdentifier == sample.identifier
                assert specimen_description.SpecimenUID == sample.uid

    def test_serialize_default_slide(self):
        # Arrange
        slide = Slide()
        schema = SlideDicomSchema()

        # Act
        serialized = schema.dump(slide)

        # Assert
        assert isinstance(serialized, Dataset)
        assert serialized.ContainerIdentifier == Defaults.string
        assert serialized.SpecimenDescriptionSequence == []
        assert_dicom_code_dataset_equals_code(
            serialized.ContainerTypeCodeSequence[0], Defaults.slide_container_type
        )

    def test_deserialize_slide(self, slide: Slide):
        # Arrange
        schema = SlideDicomSchema()
        serialized = schema.dump(slide)

        # Act
        deserialized = schema.load(serialized)

        # Assert
        assert isinstance(deserialized, Slide)
        # assert deserialized == slide

    @pytest.mark.parametrize(
        "illumination", [IlluminationColorCode("Full Spectrum"), 400.0]
    )
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
        ],
    )
    @pytest.mark.parametrize(
        "image_type", [ImageType.LABEL, ImageType.OVERVIEW, ImageType.VOLUME]
    )
    def test_serialize_wsi_metadata(
        self,
        wsi_metadata: WsiMetadata,
        equipment: Equipment,
        image: Image,
        label: Label,
        optical_path: OpticalPath,
        study: Study,
        series: Series,
        patient: Patient,
        image_type: ImageType,
    ):
        # Arrange
        schema = WsiMetadataDicomSchema(context={"image_type": image_type})

        # Act
        serialized = schema.dump(wsi_metadata)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_equipment_equals_equipment(serialized, equipment)
        assert_dicom_series_equals_series(serialized, series)
        assert_dicom_study_equals_study(serialized, study)
        assert_dicom_image_equals_image(serialized, image)
        assert_dicom_label_equals_label(serialized, label, image_type)
        assert_dicom_optical_path_equals_optical_path(
            serialized.OpticalPathSequence[0], optical_path
        )
        assert_dicom_patient_equals_patient(serialized, patient)

    def test_deserialize_wsi_metadata(
        self,
        wsi_metadata: WsiMetadata,
        equipment: Equipment,
        image: Image,
        label: Label,
        optical_path: OpticalPath,
        study: Study,
        series: Series,
        patient: Patient,
        image_type: ImageType,
        dicom_wsi_metadata: Dataset,
    ):
        # Arrange
        schema = WsiMetadataDicomSchema()

        # Act
        deserialized = schema.load(dicom_wsi_metadata)

        # Assert
        assert isinstance(deserialized, WsiMetadata)
        assert deserialized.equipment == equipment
        assert deserialized.image == image
        assert deserialized.optical_paths[0] == optical_path
        assert deserialized.study == study
        assert deserialized.series == series
        assert deserialized.patient == patient

    def test_deserialize_wsi_metadata_from_multiple_datasets(
        self,
        wsi_metadata: WsiMetadata,
        equipment: Equipment,
        image: Image,
        label: Label,
        optical_path: OpticalPath,
        study: Study,
        series: Series,
        patient: Patient,
        image_type: ImageType,
        dicom_wsi_metadata: Dataset,
        dicom_label_label: Dataset,
        dicom_overview_label: Dataset,
    ):
        # Arrange
        schema = WsiMetadataDicomSchema()
        datasets = [dicom_wsi_metadata, dicom_label_label, dicom_overview_label]

        # Act
        deserialized = schema.from_datasets(datasets)

        # Assert
        assert isinstance(deserialized, WsiMetadata)
        assert deserialized.equipment == equipment
        assert deserialized.image == image
        assert deserialized.optical_paths[0] == optical_path
        assert deserialized.study == study
        assert deserialized.series == series
        assert deserialized.patient == patient
        assert deserialized.label == label


def assert_dicom_equipment_equals_equipment(
    dicom_equipment: Dataset, equipment: Equipment
):
    assert dicom_equipment.Manufacturer == equipment.manufacturer
    assert dicom_equipment.ManufacturerModelName == equipment.model_name
    assert dicom_equipment.DeviceSerialNumber == equipment.device_serial_number
    if equipment.software_versions is not None:
        if len(equipment.software_versions) == 1:
            assert dicom_equipment.SoftwareVersions == equipment.software_versions[0]
        else:
            assert dicom_equipment.SoftwareVersions == equipment.software_versions


def assert_dicom_image_equals_image(dicom_image: Dataset, image: Image):
    assert dicom_image.AcquisitionDateTime == image.acquisition_datetime
    if image.focus_method is not None:
        assert dicom_image.FocusMethod == image.focus_method.name
    if image.extended_depth_of_field is not None:
        assert dicom_image.ExtendedDepthOfField == bool_to_dicom_literal(True)
        assert (
            dicom_image.NumberOfFocalPlanes
            == image.extended_depth_of_field.number_of_focal_planes
        )
        assert (
            dicom_image.DistanceBetweenFocalPlanes
            == image.extended_depth_of_field.distance_between_focal_planes
        )
    else:
        assert dicom_image.ExtendedDepthOfField == bool_to_dicom_literal(False)
    if image.image_coordinate_system is not None:
        assert (
            dicom_image.TotalPixelMatrixOriginSequence[0].XOffsetInSlideCoordinateSystem
            == image.image_coordinate_system.origin.x
        )
        assert (
            dicom_image.TotalPixelMatrixOriginSequence[0].YOffsetInSlideCoordinateSystem
            == image.image_coordinate_system.origin.y
        )
        assert dicom_image.ImageOrientationSlide == list(
            image.image_coordinate_system.orientation.values
        )


def assert_dicom_label_equals_label(
    dicom_label: Dataset, label: Label, image_type: ImageType
):
    assert dicom_label.LabelText == label.text
    assert dicom_label.BarcodeValue == label.barcode
    if (
        (image_type == ImageType.VOLUME and label.label_in_volume_image)
        or (image_type == ImageType.OVERVIEW and label.label_in_overview_image)
        or image_type == ImageType.LABEL
    ):
        assert dicom_label.SpecimenLabelInImage == bool_to_dicom_literal(True)
        assert dicom_label.BurnedInAnnotation == bool_to_dicom_literal(
            label.label_is_phi
        )
    else:
        assert dicom_label.SpecimenLabelInImage == bool_to_dicom_literal(False)
        assert dicom_label.BurnedInAnnotation == bool_to_dicom_literal(False)


def assert_dicom_optical_path_equals_optical_path(
    dicom_optical_path: Dataset, optical_path: OpticalPath
):
    assert dicom_optical_path.OpticalPathIdentifier == optical_path.identifier
    assert dicom_optical_path.OpticalPathDescription == optical_path.description
    if optical_path.illumination_types is not None:
        assert_dicom_code_dataset_equals_code(
            dicom_optical_path.IlluminationTypeCodeSequence[0],
            optical_path.illumination_types[0],
        )
    if isinstance(optical_path.illumination, float):
        assert dicom_optical_path.IlluminationWaveLength == optical_path.illumination
    elif isinstance(optical_path.illumination, IlluminationColorCode):
        assert_dicom_code_dataset_equals_code(
            dicom_optical_path.IlluminationColorCodeSequence[0],
            optical_path.illumination,
        )
    if optical_path.light_path_filter is not None:
        assert (
            dicom_optical_path.LightPathFilterPassThroughWavelength
            == optical_path.light_path_filter.nominal
        )
        assert dicom_optical_path.LightPathFilterPassBand == [
            optical_path.light_path_filter.low_pass,
            optical_path.light_path_filter.high_pass,
        ]
        assert_dicom_code_sequence_equals_codes(
            dicom_optical_path.LightPathFilterTypeStackCodeSequence,
            optical_path.light_path_filter.filters,
        )
    if optical_path.image_path_filter is not None:
        assert (
            dicom_optical_path.ImagePathFilterPassThroughWavelength
            == optical_path.image_path_filter.nominal
        )
        assert dicom_optical_path.ImagePathFilterPassBand == [
            optical_path.image_path_filter.low_pass,
            optical_path.image_path_filter.high_pass,
        ]
        assert_dicom_code_sequence_equals_codes(
            dicom_optical_path.ImagePathFilterTypeStackCodeSequence,
            optical_path.image_path_filter.filters,
        )
    if optical_path.objective is not None:
        assert_dicom_code_sequence_equals_codes(
            dicom_optical_path.LensesCodeSequence,
            optical_path.objective.lenses,
        )
        assert (
            dicom_optical_path.CondenserLensPower
            == optical_path.objective.condenser_power
        )
        assert (
            dicom_optical_path.ObjectiveLensPower
            == optical_path.objective.objective_power
        )
        assert (
            dicom_optical_path.ObjectiveLensNumericalAperture
            == optical_path.objective.objective_numerical_aperature
        )


def assert_dicom_patient_equals_patient(dicom_patient: Dataset, patient: Patient):
    assert dicom_patient.PatientName == patient.name
    assert dicom_patient.PatientID == patient.identifier
    assert dicom_patient.PatientBirthDate == patient.birth_date
    if patient.sex is not None:
        assert dicom_patient.PatientSex == patient.sex.name
    if isinstance(patient.species_description, str):
        assert dicom_patient.PatientSpeciesDescription == patient.species_description
    elif isinstance(patient.species_description, Code):
        assert_dicom_code_dataset_equals_code(
            dicom_patient.PatientSpeciesCodeSequence[0], patient.species_description
        )
    if patient.de_identification is not None:
        assert_dicom_bool_equals_bool(
            dicom_patient.PatientIdentityRemoved,
            patient.de_identification.identity_removed,
        )
        if patient.de_identification.methods is not None:
            string_methods = [
                method
                for method in patient.de_identification.methods
                if isinstance(method, str)
            ]
            if len(string_methods) == 1:
                assert dicom_patient.DeidentificationMethod == string_methods[0]
            elif len(string_methods) > 1:
                assert dicom_patient.DeidentificationMethod == string_methods[0]
            code_methods = [
                method
                for method in patient.de_identification.methods
                if isinstance(method, Code)
            ]
            if len(code_methods) > 1:
                assert_dicom_code_sequence_equals_codes(
                    dicom_patient.DeidentificationMethodCodeSequence, code_methods
                )


def assert_dicom_series_equals_series(dicom_series: Dataset, series: Series):
    assert dicom_series.SeriesInstanceUID == series.uid
    assert dicom_series.SeriesNumber == series.number


def assert_dicom_study_equals_study(dicom_study: Dataset, study: Study):
    assert dicom_study.StudyInstanceUID == study.uid
    assert dicom_study.StudyID == study.identifier
    assert dicom_study.StudyDate == study.date
    assert dicom_study.StudyTime == study.time
    assert dicom_study.AccessionNumber == study.accession_number
    assert dicom_study.ReferringPhysicianName == study.referring_physician_name
