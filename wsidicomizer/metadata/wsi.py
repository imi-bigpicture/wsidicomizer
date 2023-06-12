"""Complete WSI model."""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from dataclasses_json import dataclass_json

from pydicom import Dataset
from pydicom.uid import UID, generate_uid, VLWholeSlideMicroscopyImageStorage
from wsidicom.instance import ImageType
from wsidicomizer.metadata.image import Image

from wsidicomizer.metadata.model_base import ModelBase
from wsidicomizer.metadata.equipment import Equipment
from wsidicomizer.metadata.fields import FieldFactory
from wsidicomizer.metadata.label import Label
from wsidicomizer.metadata.optical_path import OpticalPath
from wsidicomizer.metadata.patient import Patient
from wsidicomizer.metadata.series import Series
from wsidicomizer.metadata.slide import Slide
from wsidicomizer.metadata.study import Study
from wsidicomizer.metadata.dicom_attribute import (
    DicomSequenceAttribute,
    DicomStringAttribute,
    DicomUidAttribute,
)

# TODO figure out how metadata defined here can override or be overriden by
# *ImageMeta*. Suggestion is to have a bool flag on each module, indicating if the
# properties defined in that module should override metadata from file.
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
class WsiMetadata(ModelBase):
    study: Optional[Study] = None
    series: Optional[Series] = None
    patient: Optional[Patient] = None
    equipment: Optional[Equipment] = None
    optical_paths: List[OpticalPath] = field(default_factory=lambda: list())
    slide: Optional[Slide] = None
    label: Optional[Label] = None
    image: Optional[Image] = None
    frame_of_reference_uid: Optional[UID] = None  # FieldFactory.uid_field()
    dimension_organization_uid: Optional[UID] = None  # FieldFactory.uid_field()
    overrides: Optional[Dict[str, bool]] = None

    def to_dataset(
        self,
        image_type: ImageType,
    ) -> Dataset:
        dataset = Dataset()
        self.insert_into_dataset(dataset, image_type)
        return dataset

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        dicom_attributes = [
            DicomUidAttribute("SOPClassUID", True, VLWholeSlideMicroscopyImageStorage),
            DicomStringAttribute("Modality", True, "SM"),
            DicomUidAttribute(
                "FrameOfReferenceUID", True, self.frame_of_reference_uid, generate_uid
            ),
            DicomStringAttribute("PositionReferenceIndicator", True, "SLIDE_CORNER"),
            DicomStringAttribute("VolumetricProperties", True, "VOLUME"),
            DicomSequenceAttribute("AcquisitionContextSequence", True, []),
            DicomSequenceAttribute(
                "DimensionOrganizationSequence",
                True,
                [
                    DicomUidAttribute(
                        "DimensionOrganizationUID",
                        True,
                        self.dimension_organization_uid,
                        generate_uid,
                    ),
                ],
            ),
        ]
        self._insert_dicom_attributes_into_dataset(dataset, dicom_attributes)

        models: List[Tuple[Optional[ModelBase], Optional[Callable[[], ModelBase]]]] = [
            (self.study, Study),
            (self.series, Series),
            (self.patient, Patient),
            (self.equipment, Equipment),
            (self.slide, Slide),
            (self.label, Label),
        ]
        if len(self.optical_paths) > 0:
            models.extend([(optical_path, None) for optical_path in self.optical_paths])
        else:
            models.append((None, OpticalPath))
        for model, model_default_factory in models:
            if model is None and model_default_factory is not None:
                model = model_default_factory()
            if model is not None:
                model.insert_into_dataset(dataset, image_type)
