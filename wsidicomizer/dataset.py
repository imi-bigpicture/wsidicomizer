#    Copyright 2021 SECTRA AB
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

"""Module containing helper methods for creating DICOM datasets."""

import datetime
from typing import Callable, List, Optional, Sequence, Tuple, Union

from highdicom.content import (
    SpecimenDescription,
    SpecimenPreparationStep,
    SpecimenSampling,
    SpecimenStaining,
)
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.sr.coding import Code
from pydicom.uid import UID as Uid
from pydicom.uid import generate_uid
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    ConceptCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
)

from opentile import Metadata


def create_base_dataset(
    modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
) -> Dataset:
    """Create a base dataset by combining module datasets with a minimal
    wsi dataset.

    Parameters
    ----------
    modules: Optional[Union[Dataset, Sequence[Dataset]]] = None

    Returns
    ----------
    Dataset
        Combined base dataset.
    """
    base_dataset = create_wsi_dataset()
    if modules is None:
        modules = create_default_modules()
    if isinstance(modules, Sequence):
        for module in modules:
            base_dataset.update(module)
    elif isinstance(modules, Dataset):
        base_dataset.update(modules)
    else:
        raise TypeError("datasets parameter should be single or list of Datasets")
    return base_dataset


def populate_base_dataset(
    metadata: Metadata, base_dataset: Dataset, include_confidential: bool = True
) -> Dataset:
    """Populate dataset with properties from tiler, if present.
    Parameters
    ----------
    metadata: Metadata
        A object holding metadata.
    base_dataset: Dataset
        Dataset to append properties to.
    include_confidential: bool = True
        If to include confidential properties (see https://dicom.nema.org/medical/dicom/current/output/html/part15.html#table_E.1-1)  # NOQA

    Returns
    ----------
    Dataset
        Dataset with added properties.
    """

    properties = {
        "Manufacturer": metadata.scanner_manufacturer,
        "ManufacturerModelName": metadata.scanner_model,
        "SoftwareVersions": metadata.scanner_software_versions,
    }
    confidential_properties = {
        "AcquisitionDateTime": metadata.aquisition_datetime,
        "DeviceSerialNumber": metadata.scanner_serial_number,
    }
    if include_confidential:
        properties.update(confidential_properties)
    for property_name, property_value in metadata.properties.items():
        if property_name == "lossy_image_compression_method":
            properties["LossyImageCompressionMethod"] = property_value
        elif property_name == "lossy_image_compression_ratio":
            properties["LossyImageCompressionRatio"] = property_value

    for property_name, property_value in properties.items():
        if not hasattr(base_dataset, property_name) and property_value is not None:
            setattr(base_dataset, property_name, property_value)
    return base_dataset


def create_wsi_dataset(uid_generator: Callable[..., Uid] = generate_uid) -> Dataset:
    """Return dataset containing (parts of) SOP common, general series, whole
    slide microscopy series, frame of reference, acquisition context,
    multi-frame dimension, and whole slide microscopy image modules.

    Some modules returned 'not complete', and completed during image data
    import or file save():
        SOP common module:
            SOPInstanceUID
        Whole slide microscopy image module:
            ImageType
            Aquisition DateTime
            SamplesPerPixel
            PhotometricInterpretation
            PlanarConfiguration
            NumberOfFrames
            BitsAllocated
            BitsStored
            HighBit
            PixelRepresentation
            LossyImageCompression (and conditionals)
            ImagedVolumeWidth
            ImagedVolumeWidth
            ImagedVolumeDepth
            TotalPixelMatrixColumns
            TotalPixelMatrixRows
            FocusMethod
            ExtendedDepthOfField (and conditionals)

    Parameters
    ----------
    uid_generator: Callable[..., Uid] = generate_uid
        Function that can generate Uids.

    Returns
    ----------
    Dataset
        WSI dataset.
    """
    dataset = Dataset()

    # SOP common module (SOPInstanceUID written on save())
    dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.77.1.6"

    # dataset.StudyInstanceUID = uid_generator()
    # General series and Whole slide Microscopy modules
    dataset.SeriesNumber = ""
    dataset.SeriesInstanceUID = uid_generator()
    dataset.Modality = "SM"

    # Frame of reference module
    dataset.FrameOfReferenceUID = uid_generator()
    dataset.PositionReferenceIndicator = "SLIDE_CORNER"

    # Acquisition context module (empty)
    dataset.AcquisitionContextSequence = DicomSequence()

    # Multi-frame Dimension module
    dimension_organization_uid = uid_generator()
    dimension_organization_sequence = Dataset()
    dimension_organization_sequence.DimensionOrganizationUID = (
        dimension_organization_uid
    )
    dataset.DimensionOrganizationSequence = DicomSequence(
        [dimension_organization_sequence]
    )

    # Whole slide micropscopy image module (most filled when importing file)
    dataset.BurnedInAnnotation = "NO"
    dataset.SpecimenLabelInImage = "NO"
    dataset.VolumetricProperties = "VOLUME"
    # AcquisitionDateTime is required
    dt = datetime.datetime.now()
    dataset.AcquisitionDateTime = dt.strftime("%Y%m%d%H%M%S.%f")

    return dataset


def create_study_module(
    study_id: str = "",
    study_date: Optional[datetime.date] = None,
    study_time: Optional[datetime.time] = None,
    study_accession_number: str = "",
    referring_physician_name: str = "",
    uid_generator: Callable[..., Uid] = generate_uid,
) -> Dataset:
    """Create general study module.

    Parameters
    ----------
    study_id: str = ""
        Study identifier. Can be empty.
    Optional[datetime.date] = None
        Date the study started. Can be empty.
    Optional[datetime.time] = None
        Time the study started. Can be empty.
    accession_number: str = ""
        Order for the study. Can be empty.
    referring_physician_name: str = ""
        Name of reffering physician. Can be empty.

    Returns
    ----------
    Dataset
        Dataset containing general study module.
    """
    dataset = Dataset()
    dataset.StudyInstanceUID = uid_generator()
    dataset.StudyID = study_id
    dataset.StudyDate = study_date
    dataset.StudyTime = study_time
    dataset.AccessionNumber = study_accession_number
    dataset.ReferringPhysicianName = referring_physician_name
    return dataset


def create_patient_module(
    name: str = "",
    id: str = "",
    birth_date: Optional[datetime.date] = None,
    sex: str = "",
    identity_removed: bool = False,
    de_indentification_methods: Optional[Sequence[Union[str, Code]]] = None,
    age_at_extraction: Optional[str] = None,
) -> Dataset:
    """Create patient and patient study modules.

    Parameters
    ----------
    name: str = ""
        Patient's full name. Can be empty.
    id: str = ""
        Primary identifier for the Patient. Can be empty.
    birth_date: str = ""
        Birth date of the Patient. Can be empty.
    sex: str = ""
        Sex of the named Patient. F/M/O. Can be empty.
    identity_removed: bool = False
        True if partient idendity has been removed from attributes in dataset
        and in image data.
    de_indentification_methods: Optional[Sequence[Union[str, Code]]] = None
        Method of de-indentification. Can be descriptive strings and/or coded
        values.
    age_at_extraction: Optional[str] = None
        Age of the Patient at extraction.

    Returns
    ----------
    Dataset
        Dataset containing patient and patient study modules.
    """
    if de_indentification_methods is None:
        de_indentification_methods = []
    dataset = Dataset()
    dataset.PatientName = name
    dataset.PatientID = id
    dataset.PatientBirthDate = birth_date
    dataset.PatientSex = sex
    dataset.PatientIdentityRemoved = "YES" if identity_removed else "NO"
    if identity_removed and de_indentification_methods is None:
        raise ValueError(
            "de-intification method must be specified if "
            "patient identity has been removed"
        )
    de_indentification_method_strings: List[str] = []
    de_indentification_method_codes: List[Code] = []

    for de_indentification_method in de_indentification_methods:
        if isinstance(de_indentification_method, str):
            de_indentification_method_strings.append(de_indentification_method)
        elif isinstance(de_indentification_method, Code):
            de_indentification_method_codes.append(de_indentification_method)
        else:
            raise TypeError(
                "De-indentification methods should be string or coded value"
            )
    if de_indentification_method_strings != []:
        dataset.DeidentificationMethod = de_indentification_method_strings
    if de_indentification_method_codes != []:
        dataset.DeidentificationMethodCodeSequence = DicomSequence(
            [
                ConceptCode.from_code(de_indentification_method_code).to_ds()
                for de_indentification_method_code in de_indentification_method_codes
            ]
        )
    if age_at_extraction is not None:
        dataset.PatientAge = age_at_extraction

    return dataset


def create_device_module(
    manufacturer: str = "Unknown",
    model_name: str = "Unknown",
    serial_number: str = "Unknown",
    software_versions: Sequence[str] = ["Unknown"],
) -> Dataset:
    """Create extended equipment module.

    Parameters
    ----------
    manufacturer: str = 'Unknown'.
        Manufacturer of the equipment.
    model_name: str = 'Unknown'
        Manufacturer's model name of the equipment.
    serial_number: str = 'Unknown'
        Manufacturer's serial number of the equipment.
    software_versions: Sequence[str] = ['Unknown']
        Software version of the equipment.

    Returns
    ----------
    Dataset
        Dataset containing extended equipment module.
    """
    dataset = Dataset()
    properties = {
        "Manufacturer": manufacturer,
        "ManufacturerModelName": model_name,
        "DeviceSerialNumber": serial_number,
        "SoftwareVersions": software_versions,
    }
    for name, value in properties.items():
        setattr(dataset, name, value)
    return dataset


def create_sample(
    sample_id: str,
    stainings: Optional[Sequence[str]] = None,
    embedding_medium: Optional[str] = None,
    fixative: Optional[str] = None,
    specimen_id: Optional[str] = None,
    specimen_type: Optional[str] = None,
    specimen_sampling_method: Optional[str] = None,
    anatomical_sites: Optional[Sequence[Tuple[Code, Sequence[Code]]]] = None,
    location: Optional[Union[str, Tuple[float, float, float]]] = None,
    uid_generator: Callable[..., Uid] = generate_uid,
) -> Dataset:
    """Create sample description.

    Parameters
    ----------
    sample_id: str
        Identifier for the sample.
    stainings: Optional[str] = None
        Stainings used. See SpecimenStainsCode.list() for allowed values.
    embedding_medium: Optional[str] = None
        Embedding medium used. See SpecimenEmbeddingMediaCode.list() for
        allowed values.
    fixative: Optional[str] = None
        Fixative used. See SpecimenFixativesCode.list() for allowed values.
    specimen_id: Optional[str] = None
        Identifier for the specimen the sample was sampled from.
    specimen_type: Optional[str] = None
        Anatotomic type of specimen the sample was sampled from. See
        AnatomicPathologySpecimenTypesCode.list() for allowed values.
    specimen_sampling_method: Optional[str] = None
        Sampling method used for sampling the sample from the specimen. See
        SpecimenSamplingProcedureCode.list() for allowed values.
    anatomical_sites: Optional[Sequence[Tuple[Code, Sequence[Code]]]] = None
        List of original anatomical sites, each defined by a code and optional
        list of modifier codes.
    location: Optional[Union[str, Tuple[float, float, float]]] = None
        Location of sample in slide, defined either by descriptive string
        or xyz-coordinates.
    uid_generator: Callable[..., Uid] = generate_uid
        Function that can generate uids.

    Returns
    ----------
    Dataset
        Dataset containing a sample description.
    """
    sample_preparation_steps: List[SpecimenPreparationStep] = []
    if stainings is not None:
        sample_preparation_step = create_sample_preparation_step(
            sample_id, stainings, embedding_medium, fixative
        )
        sample_preparation_steps.append(sample_preparation_step)
    if specimen_id is not None:
        sample_sampling_step = create_sample_sampling_step(
            sample_id, specimen_id, specimen_sampling_method, specimen_type
        )
        sample_preparation_steps.append(sample_sampling_step)

    specimen = SpecimenDescription(
        specimen_id=sample_id,
        specimen_uid=uid_generator(),
        specimen_preparation_steps=sample_preparation_steps,
        specimen_location=location,
    )
    if anatomical_sites is not None:
        specimen = add_anatomical_sites_to_specimen(specimen, anatomical_sites)

    return specimen


def create_sample_preparation_step(
    specimen_id: str,
    stainings: Sequence[str],
    embedding_medium: Optional[str],
    fixative: Optional[str],
) -> SpecimenPreparationStep:
    """Create SpecimenPreparationStep for a preparation step.

    Parameters
    ----------
    specimen_id: str
        ID of specimen that has been prepared.
    stainings: Sequence[str]
        Sequence of stainings used.
    embedding_medium: Optional[str] = None
        Embedding medium used.
    fixative: Optional[str] = None
        Fixative used.

    Returns
    ----------
    SpecimenPreparationStep
        SpecimenPreparationStep for a preparation step.
    """
    if embedding_medium is not None:
        embedding_medium_code = SpecimenEmbeddingMediaCode(embedding_medium).code
    else:
        embedding_medium_code = None
    if fixative is not None:
        fixative_code = SpecimenFixativesCode(fixative).code
    else:
        fixative_code = None

    processing_procedure = SpecimenStaining(
        [SpecimenStainsCode(staining).code for staining in stainings]
    )
    sample_preparation_step = SpecimenPreparationStep(
        specimen_id=specimen_id,
        processing_procedure=processing_procedure,
        embedding_medium=embedding_medium_code,
        fixative=fixative_code,
    )
    return sample_preparation_step


def create_sample_sampling_step(
    sample_id: str,
    specimen_id: str,
    specimen_sampling_method: Optional[str],
    specimen_type: Optional[str],
) -> SpecimenPreparationStep:
    """Create SpecimenPreparationStep for a sampling step.

    Parameters
    ----------
    sample_id: str
        ID of sample that has been created.
    specimen_id: str
        ID of specimen that was sampled.
    specimen_sampling_method: Optional[str]
        Method used to sample specimen.
    specimen_type: Optional[str]
        Type of specimen that was sampled

    Returns
    ----------
    SpecimenPreparationStep
        SpecimenPreparationStep for a sampling step.
    """
    if specimen_sampling_method is None:
        raise ValueError(
            "Specimen sampling method required if " "specimen id is defined"
        )
    if specimen_type is None:
        raise ValueError("Specimen type required if " "specimen id is defined")
    specimen_type_code = AnatomicPathologySpecimenTypesCode(specimen_type)
    sampling_method_code = SpecimenSamplingProcedureCode(specimen_sampling_method)
    sample_sampling_step = SpecimenPreparationStep(
        specimen_id=sample_id,
        processing_procedure=SpecimenSampling(
            method=sampling_method_code.code,
            parent_specimen_id=specimen_id,
            parent_specimen_type=specimen_type_code.code,
        ),
    )
    return sample_sampling_step


def add_anatomical_sites_to_specimen(
    specimen: Dataset, anatomical_sites: Sequence[Tuple[Code, Sequence[Code]]]
) -> Dataset:
    """Add anatomical site and anatomical site modifier codes to specimen.

    Parameters
    ----------
    specimen: Dataset
        Dataset containing a specimen description
    anatomical_sites: Sequence[Tuple[Code, Sequence[Code]]]
        List of original anatomical sites, each defined by a code and
        list of modifier codes (can be empty).

    Returns
    ----------
    Dataset
        Dataset containing a specimen description.
    """
    anatomical_site_datasets: List[Dataset] = []
    for anatomical_site, modifiers in anatomical_sites:
        anatomical_site_dataset = ConceptCode.from_code(anatomical_site).to_ds()

        if modifiers != []:
            modifier_datasets: List[Dataset] = []
            for modifier in modifiers:
                modifier_dataset = Dataset()
                modifier_dataset.CodeValue = modifier.value
                modifier_dataset.CodingSchemeDesignator = modifier.scheme_designator
                modifier_dataset.CodeMeaning = modifier.meaning
                modifier_datasets.append(modifier_dataset)

            (
                anatomical_site_dataset.PrimaryAnatomicStructureModifierSequence
            ) = DicomSequence(modifier_datasets)
        anatomical_site_datasets.append(anatomical_site_dataset)
    specimen.PrimaryAnatomicStructureSequence = DicomSequence(anatomical_site_datasets)
    return specimen


def create_specimen_module(
    slide_id: str, samples: Union[Dataset, Sequence[Dataset]]
) -> Dataset:
    """Create specimen module.

    Parameters
    ----------
    slide_id: str.
        Identifier for the slide.
    samples: Union[Dataset, Sequence[Dataset]]
        Single or list of sample descriptions (should be created with
        create_sample())

    Returns
    ----------
    Dataset
        Dataset containing specimen module.
    """
    dataset = Dataset()
    dataset.ContainerIdentifier = slide_id
    dataset.IssuerOfTheContainerIdentifierSequence = DicomSequence()

    container_type_code_sequence = Dataset()
    container_type_code_sequence.CodeValue = "258661006"
    container_type_code_sequence.CodingSchemeDesignator = "SCT"
    container_type_code_sequence.CodeMeaning = "Slide"
    dataset.ContainerTypeCodeSequence = DicomSequence([container_type_code_sequence])

    container_component_sequence = Dataset()
    container_component_sequence.ContainerComponentMaterial = "GLASS"
    container_component_type_code_sequence = Dataset()
    container_component_type_code_sequence.CodeValue = "433472003"
    container_component_type_code_sequence.CodingSchemeDesignator = "SCT"
    container_component_type_code_sequence.CodeMeaning = "Microscope slide coverslip"
    container_component_sequence.ContainerComponentTypeCodeSequence = DicomSequence(
        [container_component_type_code_sequence]
    )
    dataset.ContainerComponentSequence = DicomSequence([container_component_sequence])
    if not isinstance(samples, Sequence):
        samples = [samples]
    specimen_description_sequence = DicomSequence(samples)
    dataset.SpecimenDescriptionSequence = specimen_description_sequence

    return dataset


def create_brightfield_optical_path_module(
    magnification: Optional[float] = None,
) -> Dataset:
    """Create optical path module for brightfield illumination conditions.

    Parameters
    ----------
    magnification: Optional[float] = None
        Objective magnification.

    Returns
    ----------
    Dataset
        Dataset containing optical path module for brightfield illumination.
    """
    dataset = Dataset()
    optical_path_item = Dataset()
    optical_path_item.OpticalPathIdentifier = "0"
    illumination_type_code_sequence = Dataset()
    illumination_type_code_sequence.CodeValue = "111744"
    illumination_type_code_sequence.CodingSchemeDesignator = "DCM"
    illumination_type_code_sequence.CodeMeaning = "Brightfield illumination"
    optical_path_item.IlluminationTypeCodeSequence = DicomSequence(
        [illumination_type_code_sequence]
    )
    illumination_color_code_sequence = Dataset()
    illumination_color_code_sequence.CodeValue = "R-102C0"
    illumination_color_code_sequence.CodingSchemeDesignator = "SRT"
    illumination_color_code_sequence.CodeMeaning = "Full Spectrum"
    optical_path_item.IlluminationColorCodeSequence = DicomSequence(
        [illumination_color_code_sequence]
    )
    if magnification is not None:
        optical_path_item.ObjectiveLensPower = magnification

    dataset.OpticalPathSequence = DicomSequence([optical_path_item])

    return dataset


def create_default_modules(
    uid_generator: Callable[..., Uid] = generate_uid
) -> List[Dataset]:
    """Return default module dataset for testing.

    Parameters
    ----------
    uid_generator: Callable[..., Uid]
        Function that can generate Uids.

    Returns
    ----------
    List[Dataset]
        Default module datasets.
    """
    modules: List[Dataset] = []

    # Generic study module
    modules.append(create_study_module())

    # Generic patient module
    modules.append(create_patient_module())

    # Generic device module
    modules.append(create_device_module())

    # Generic specimen module
    modules.append(
        create_specimen_module(
            "Unknown",
            samples=[
                create_sample(
                    sample_id="Unknown",
                    stainings=["water soluble eosin stain", "hematoxylin stain"],
                    uid_generator=uid_generator,
                )
            ],
        )
    )

    # Generic optical path sequence
    modules.append(create_brightfield_optical_path_module())

    return modules
