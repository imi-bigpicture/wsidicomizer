import pytest
from pydicom import Dataset
from pydicom.sr.coding import Code
from pydicom.valuerep import DT
from wsidicom.conceptcode import IlluminationColorCode
from wsidicom.instance import ImageType

from tests.metadata.helpers import bool_to_dicom_literal, code_to_code_dataset
from wsidicomizer.metadata import (
    Equipment,
    Image,
    OpticalPath,
    Patient,
    Series,
    Slide,
    Study,
    WsiMetadata,
)
from wsidicomizer.metadata.dicom_schema.slide import SlideDicomSchema


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
    if image.focus_method is not None:
        dataset.FocusMethod = image.focus_method.name
    if image.image_coordinate_system is not None:
        dataset.ImageOrientationSlide = list(
            image.image_coordinate_system.orientation.values
        )
        origin = Dataset()
        origin.XOffsetInSlideCoordinateSystem = image.image_coordinate_system.origin.x
        origin.YOffsetInSlideCoordinateSystem = image.image_coordinate_system.origin.y

        dataset.TotalPixelMatrixOriginSequence = [origin]
    if image.extended_depth_of_field is not None:
        dataset.ExtendedDepthOfField = "YES"
        dataset.NumberOfFocalPlanes = (
            image.extended_depth_of_field.number_of_focal_planes
        )
        dataset.DistanceBetweenFocalPlanes = (
            image.extended_depth_of_field.distance_between_focal_planes
        )
    else:
        dataset.ExtendedDepthOfField = "NO"
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
    if isinstance(optical_path.illumination, (int, float)):
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
