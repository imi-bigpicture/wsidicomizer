from datetime import datetime
from typing import Optional, Sequence, Type

import pytest
from pydicom import Dataset
from pydicom.sr.coding import Code
from pydicom.valuerep import DT, DSfloat
from wsidicom.conceptcode import IlluminationColorCode
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
)
from wsidicomizer.metadata.defaults import Defaults
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    BooleanDicomField,
    FlatteningNestedField,
)
from wsidicomizer.metadata.dicom_schema.equipment import EquipmentDicomSchema
from wsidicomizer.metadata.dicom_schema.image import ImageDicomSchema
from wsidicomizer.metadata.dicom_schema.label import LabelDicomSchema
from wsidicomizer.metadata.dicom_schema.optical_path import OpticalPathDicomSchema
from wsidicomizer.metadata.dicom_schema.patient import PatientDicomSchema
from wsidicomizer.metadata.dicom_schema.series import SeriesDicomSchema
from wsidicomizer.metadata.dicom_schema.slide import SlideDicomSchema
from wsidicomizer.metadata.dicom_schema.study import StudyDicomSchema
from wsidicomizer.metadata.dicom_schema.wsi import WsiMetadataDicomSchema
from wsidicomizer.metadata.json_schema.series import SeriesSchema


class TestDicomMetadata:
    @pytest.mark.parametrize(
        ["manufacturer", "model_name", "serial_number", "versions"],
        [
            ["manufacturer", "model_name", "serial_number", ["version"]],
            ["manufacturer", "model_name", "serial_number", ["version 1", "version 2"]],
        ],
    )
    def test_serialize_dicom_eqipment(self, equipment: Equipment):
        # Arrange
        model = EquipmentDicomSchema()
        assert equipment.software_versions is not None

        # Act
        serialized = model.dump(equipment)

        # Assert
        assert isinstance(serialized, Dataset)
        assert_dicom_equipment_equals_equipment(serialized, equipment)

    def test_serialize_dicom_eqipment_default(self):
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

    @pytest.mark.parametrize(
        "illumination", [IlluminationColorCode("Full Spectrum"), 400.0]
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
        print(serialized)
        if slide.samples is not None:
            assert len(serialized.SpecimenDescriptionSequence) == len(slide.samples)
            for specimen_description, sample in zip(
                serialized.SpecimenDescriptionSequence, slide.samples
            ):
                assert specimen_description.SpecimenIdentifier == sample.identifier
                assert specimen_description.SpecimenUID == sample.uid

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
    assert dicom_patient.PatientSex == patient.sex.name
    if isinstance(patient.species_description, str):
        assert dicom_patient.PatientSpeciesDescription == patient.species_description
    elif isinstance(patient.species_description, Code):
        assert_dicom_code_dataset_equals_code(
            dicom_patient.PatientSpeciesCodeSequence[0], patient.species_description
        )
    assert_dicom_bool_equals_bool(
        dicom_patient.PatientIdentityRemoved,
        patient.de_identification.identity_removed,
    )
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


@pytest.fixture()
def dicom_equipment(equipment: Equipment):
    dataset = Dataset()
    dataset.Manufacturer = equipment.manufacturer
    dataset.ManufacturerModelName = equipment.model_name
    dataset.DeviceSerialNumber = equipment.device_serial_number
    dataset.SoftwareVersions = equipment.software_versions
    yield dataset


@pytest.fixture()
def dicom_image(image: Image):
    dataset = Dataset()
    dataset.AcquisitionDateTime = DT(image.acquisition_datetime)
    dataset.FocusMethod = image.focus_method.name
    dataset.ImageOrientationSlide = list(
        image.image_coordinate_system.orientation.values
    )
    origin = Dataset()
    origin.XOffsetInSlideCoordinateSystem = image.image_coordinate_system.origin.x
    origin.YOffsetInSlideCoordinateSystem = image.image_coordinate_system.origin.y

    dataset.TotalPixelMatrixOriginSequence = [origin]
    dataset.ExtendedDepthOfField = "YES"
    dataset.NumberOfFocalPlanes = image.extended_depth_of_field.number_of_focal_planes
    dataset.DistanceBetweenFocalPlanes = (
        image.extended_depth_of_field.distance_between_focal_planes
    )
    yield dataset


@pytest.fixture()
def dicom_optical_path(optical_path: OpticalPath):
    dataset = Dataset()
    dataset.OpticalPathIdentifier = optical_path.identifier
    dataset.OpticalPathDescription = optical_path.description
    if optical_path.illumination_types is not None:
        dataset.IlluminationTypeCodeSequence = [
            illumination_type.to_ds()
            for illumination_type in optical_path.illumination_types
        ]
    if isinstance(optical_path.illumination, float):
        dataset.IlluminationWaveLength = optical_path.illumination
    elif isinstance(optical_path.illumination, IlluminationColorCode):
        dataset.IlluminationColorCodeSequence = [optical_path.illumination.to_ds()]

    if optical_path.light_path_filter is not None:
        dataset.LightPathFilterPassThroughWavelength = (
            optical_path.light_path_filter.nominal
        )
        dataset.LightPathFilterPassBand = [
            optical_path.light_path_filter.low_pass,
            optical_path.light_path_filter.high_pass,
        ]
        dataset.LightPathFilterTypeStackCodeSequence = [
            filter.to_ds() for filter in optical_path.light_path_filter.filters
        ]
    if optical_path.image_path_filter is not None:
        dataset.ImagePathFilterPassThroughWavelength = (
            optical_path.image_path_filter.nominal
        )
        dataset.ImagePathFilterPassBand = [
            optical_path.image_path_filter.low_pass,
            optical_path.image_path_filter.high_pass,
        ]
        dataset.ImagePathFilterTypeStackCodeSequence = [
            filter.to_ds() for filter in optical_path.image_path_filter.filters
        ]
    if optical_path.objective is not None:
        dataset.LensesCodeSequence = [
            lense.to_ds() for lense in optical_path.objective.lenses
        ]

        dataset.CondenserLensPower = optical_path.objective.condenser_power
        dataset.ObjectiveLensPower = optical_path.objective.objective_power
        dataset.ObjectiveLensNumericalAperture = (
            optical_path.objective.objective_numerical_aperature
        )
    yield dataset


@pytest.fixture()
def dicom_patient(patient: Patient):
    dataset = Dataset()
    dataset.PatientName = patient.name
    dataset.PatientID = patient.identifier
    dataset.PatientBirthDate = patient.birth_date
    dataset.PatientSex = patient.sex.name
    if isinstance(patient.species_description, str):
        dataset.PatientSpeciesDescription = patient.species_description
    elif isinstance(patient.species_description, Code):
        dataset.PatientSpeciesCodeSequence = [
            code_to_code_dataset(patient.species_description)
        ]
    dataset.PatientIdentityRemoved = bool_to_dicom_literal(
        patient.de_identification.identity_removed
    )
    dataset.DeidentificationMethod = [
        method
        for method in patient.de_identification.methods
        if isinstance(method, str)
    ]
    dataset.DeidentificationMethodCodeSequence = [
        code_to_code_dataset(method)
        for method in patient.de_identification.methods
        if isinstance(method, Code)
    ]
    yield dataset


@pytest.fixture()
def dicom_series(series: Series):
    dataset = Dataset()
    dataset.SeriesInstanceUID = series.uid
    dataset.SeriesNumber = series.number
    yield dataset


@pytest.fixture()
def dicom_study(study: Study):
    dataset = Dataset()
    dataset.StudyInstanceUID = study.uid
    dataset.StudyID = study.identifier
    dataset.StudyDate = study.date
    dataset.StudyTime = study.time
    dataset.AccessionNumber = study.accession_number
    dataset.ReferringPhysicianName = study.referring_physician_name
    yield dataset


@pytest.fixture()
def dicom_slide(slide: Slide):
    schema = SlideDicomSchema()
    yield schema.dump(slide)


@pytest.fixture()
def dicom_wsi_metadata(
    wsi_metadata: WsiMetadata,
    dicom_equipment: Dataset,
    dicom_image: Dataset,
    # dicom_label: Dataset,
    dicom_slide: Dataset,
    dicom_optical_path: Dataset,
    dicom_study: Dataset,
    dicom_series: Dataset,
    dicom_patient: Dataset,
    image_type: ImageType,
):
    dataset = Dataset()
    dataset.update(dicom_equipment)
    dataset.update(dicom_image)
    # dataset.update(dicom_label)
    dataset.update(dicom_slide)
    dataset.update(dicom_study)
    dataset.update(dicom_series)
    dataset.update(dicom_patient)
    dataset.OpticalPathSequence = [dicom_optical_path]
    dataset.ImageType = ["ORIGINAL", "PRIMIARY", image_type.value]
    dimension_organization = Dataset()
    dimension_organization.DimensionOrganizationUID = (
        wsi_metadata.dimension_organization_uid
    )
    dataset.DimensionOrganizationSequence = [dimension_organization]
    dataset.FrameOfReferenceUID = wsi_metadata.frame_of_reference_uid
    yield dataset
