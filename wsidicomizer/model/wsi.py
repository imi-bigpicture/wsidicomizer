import datetime
from dataclasses import dataclass, field
from typing import List

from opentile import Metadata as ImageMetadata
from pydicom import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import UID, generate_uid
from wsidicom.instance import ImageType
from wsidicom.optical import OpticalPath

from wsidicomizer.model.base import DicomModelBase
from wsidicomizer.model.equipment import Equipment
from wsidicomizer.model.label import Label
from wsidicomizer.model.patient import Patient
from wsidicomizer.model.series import Series
from wsidicomizer.model.slide import Slide
from wsidicomizer.model.study import Study

# TODO figure out how metadata defined here can override or be overriden by
# *ImageMeta*. Suggestion is to have a bool flag on each module, indicating if the
# properties defined in that module should override metadata from fil.
# Could additionally add a *override* dict that specifies individual attributes that
# should override metadata from file. All attributes not set to override will be
# overridden by attributes from file.

# Use case 1: User wants to set the attributes in Equipment so that no attributes from
# file is used (User does not want to make it to easy to figure out what scanner was
# used). User would then set the override-property of the Equpment object to True.

# Use case 2: User wants to set the device serial number attribute in Equipment, but
# allow the other attributes to be filled in from file. User would then set the
# value for key 'device_serial_number' in the override_property-dictionary to True.

# The same override-dictionary could be used in all modules, e.g. one could create a
# override-dictionary:
# overrides = {
#   'device_serial_number': True,
#   'label_text': True
# }
# And feed this to all modules.

# The modules primarily contain type 1 and 2 attributes, but also some 3 and some
# conditional attributes. They way they are currenly converted to dataset, there is no
# check that type 1 attributes are not empty, or that type 3 attributes are not included
# if empty, or if conditional attributes are set. The straight forward way is likely to
# change to model-specific to_dataset()-methods.

# Names in DICOM has a specific format, which is not super intuitive to make from
# scratch. Maybe use the pydicom dicom name class, as one can then use its helper
# function to format the name correctly.


@dataclass
class WsiMetadata:
    study: Study = field(default_factory=lambda: Study())
    series: Series = field(default_factory=lambda: Series())
    patient: Patient = field(default_factory=lambda: Patient())
    equipment: Equipment = field(default_factory=lambda: Equipment())
    optical_paths: List[OpticalPath] = field(default_factory=lambda: list())
    slide: Slide = field(default_factory=lambda: Slide())
    label: Label = field(default_factory=lambda: Label())
    frame_of_reference_uid: UID = generate_uid()
    dimension_organization_uid: UID = generate_uid()
    acquisition_datetime: datetime.datetime = datetime.datetime.now()
    label_in_volume_image: bool = False
    label_in_overview_image: bool = False
    label_is_phi: bool = True

    def to_dataset(
        self,
        image_type: ImageType,
        image_metadata: ImageMetadata,
        include_confidential_from_image_metadata: bool = True,
    ) -> Dataset:
        dataset = Dataset()
        # SOP common module
        dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.77.1.6"

        # General series and Whole slide Microscopy modules
        dataset.SeriesNumber = ""
        dataset.Modality = "SM"

        # Frame of reference module
        dataset.FrameOfReferenceUID = self.frame_of_reference_uid
        dataset.PositionReferenceIndicator = "SLIDE_CORNER"

        # Acquisition context module (empty)
        dataset.AcquisitionContextSequence = DicomSequence()

        # Multi-frame Dimension module
        dimension_organization_sequence = Dataset()
        dimension_organization_sequence.DimensionOrganizationUID = (
            self.dimension_organization_uid
        )
        dataset.DimensionOrganizationSequence = DicomSequence(
            [dimension_organization_sequence]
        )

        # Whole slide micropscopy image module (most filled when importing file)
        label_in_image = "NO"
        contains_phi = "NO"
        if (
            (image_type == ImageType.VOLUME and self.label_in_volume_image)
            or (image_type == ImageType.OVERVIEW and self.label_in_overview_image)
            or image_type == ImageType.LABEL
        ):
            label_in_image = "YES"
            contains_phi = "YES" if self.label_is_phi else "NO"
        dataset.BurnedInAnnotation = contains_phi
        dataset.SpecimenLabelInImage = label_in_image

        dataset.VolumetricProperties = "VOLUME"
        dataset.AcquisitionDateTime = self.acquisition_datetime.strftime(
            "%Y%m%d%H%M%S.%f"
        )
        modules: List[DicomModelBase] = [
            self.study,
            self.series,
            self.patient,
            self.equipment,
        ]
        for module in modules:
            dataset.update(module.to_dataset())
        dataset.OpticalPathSequence = DicomSequence(
            [optical_path.to_ds() for optical_path in self.optical_paths]
        )
        dataset.update(self.slide.to_dataset())

        # TODO clean up
        properties = {
            "Manufacturer": image_metadata.scanner_manufacturer,
            "ManufacturerModelName": image_metadata.scanner_model,
            "SoftwareVersions": image_metadata.scanner_software_versions,
        }
        confidential_properties = {
            "AcquisitionDateTime": image_metadata.aquisition_datetime,
            "DeviceSerialNumber": image_metadata.scanner_serial_number,
        }
        if include_confidential_from_image_metadata:
            properties.update(confidential_properties)
        for property_name, property_value in image_metadata.properties.items():
            if property_name == "lossy_image_compression_method":
                properties["LossyImageCompressionMethod"] = property_value
            elif property_name == "lossy_image_compression_ratio":
                properties["LossyImageCompressionRatio"] = property_value

        for property_name, property_value in properties.items():
            if not hasattr(dataset, property_name) and property_value is not None:
                setattr(dataset, property_name, property_value)
        return dataset
