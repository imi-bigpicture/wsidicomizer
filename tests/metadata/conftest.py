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

import datetime
from typing import Optional, Sequence, Union

import numpy as np
import pytest
from pydicom.uid import UID
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    Code,
    IlluminationCode,
    IlluminationColorCode,
    ImagePathFilterCode,
    LenseCode,
    LightPathFilterCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationStepsCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
    UnitCode,
)
from wsidicom.metadata import (
    Collection,
    ConstantLutSegment,
    Embedding,
    Equipment,
    ExtendedDepthOfField,
    Fixation,
    FocusMethod,
    Image,
    ImageCoordinateSystem,
    ImagePathFilter,
    Label,
    LightPathFilter,
    LinearLutSegment,
    Lut,
    Measurement,
    Objectives,
    OpticalPath,
    Patient,
    PatientDeIdentification,
    PatientSex,
    Processing,
    Pyramid,
    Sample,
    SampleLocalization,
    Series,
    Slide,
    SlideSample,
    Specimen,
    Staining,
    Study,
    WsiMetadata,
)


@pytest.fixture
def manufacturer():
    yield "manufacturer"


@pytest.fixture
def model_name():
    yield "model name"


@pytest.fixture
def serial_number():
    yield "serial number"


@pytest.fixture
def versions():
    yield ["versions"]


@pytest.fixture()
def equipment(
    manufacturer: Optional[str],
    model_name: Optional[str],
    serial_number: Optional[str],
    versions: Optional[Sequence[str]],
):
    yield Equipment(
        manufacturer,
        model_name,
        serial_number,
        versions,
    )


@pytest.fixture()
def image(
    acquisition_datetime: Optional[datetime.datetime],
    focus_method: Optional[FocusMethod],
    extended_depth_of_field: Optional[ExtendedDepthOfField],
    image_coordinate_system: Optional[ImageCoordinateSystem],
):
    yield Image(
        acquisition_datetime,
        focus_method,
        extended_depth_of_field,
        image_coordinate_system,
    )


@pytest.fixture()
def label():
    yield Label("text", "barcode", contains_phi=True)


@pytest.fixture()
def light_path_filter():
    yield LightPathFilter(
        [LightPathFilterCode("Green optical filter")],
        500,
        400,
        600,
    )


@pytest.fixture()
def image_path_filter():
    yield ImagePathFilter(
        [
            ImagePathFilterCode("Red optical filter"),
        ],
        500,
        400,
        600,
    )


@pytest.fixture()
def objectives():
    yield Objectives([LenseCode("High power non-immersion lens")], 10.0, 20.0, 0.5)


@pytest.fixture()
def lut():
    yield Lut(
        [ConstantLutSegment(0, 256)],
        [ConstantLutSegment(0, 256)],
        [LinearLutSegment(0, 255, 256)],
        np.uint16,
    )


@pytest.fixture()
def optical_path(
    illumination: Union[IlluminationColorCode, float],
    light_path_filter: LightPathFilter,
    image_path_filter: ImagePathFilter,
    objectives: Objectives,
    lut: Lut,
):
    yield OpticalPath(
        "identifier",
        "description",
        [IlluminationCode("Brightfield illumination")],
        illumination,
        None,
        lut,
        light_path_filter,
        image_path_filter,
        objectives,
    )


@pytest.fixture(
    params=[
        ["specimen description", "method"],
        [Code("value", "scheme", "meaning"), Code("value", "scheme", "meaning")],
    ]
)
def patient(request):
    species_description = request.param[0]
    assert isinstance(species_description, (str, Code))
    method = request.param[1]
    assert isinstance(method, (str, Code))
    patient_deidentification = PatientDeIdentification(True, [method])
    yield Patient(
        "name",
        "identifier",
        datetime.datetime(2023, 8, 5),
        PatientSex.O,
        species_description,
        patient_deidentification,
    )


@pytest.fixture()
def collection():
    yield Collection(
        SpecimenCollectionProcedureCode("Excision"),
        datetime.datetime(2023, 8, 5),
        "description",
    )


@pytest.fixture()
def extracted_specimen(collection: Collection):
    yield Specimen(
        "specimen",
        collection,
        AnatomicPathologySpecimenTypesCode("Gross specimen"),
    )


@pytest.fixture()
def sample(extracted_specimen: Specimen):
    processing = Processing(
        SpecimenPreparationStepsCode("Specimen clearing"),
        datetime.datetime(2023, 8, 5),
    )
    yield Sample(
        "sample",
        [
            extracted_specimen.sample(
                SpecimenSamplingProcedureCode("Dissection"),
                datetime.datetime(2023, 8, 5),
                "Sampling to block",
            ),
        ],
        AnatomicPathologySpecimenTypesCode("Tissue section"),
        [processing],
    )


@pytest.fixture()
def slide_sample(sample: Sample):
    yield SlideSample(
        "slide sample",
        [Code("value", "scheme", "meaning")],
        sample.sample(
            SpecimenSamplingProcedureCode("Block sectioning"),
            datetime.datetime(2023, 8, 5),
            "Sectioning to slide",
        ),
        uid=UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"),
        localization=SampleLocalization(description="left"),
    )


@pytest.fixture()
def slide():
    part_1 = Specimen(
        "part 1",
        Collection(
            SpecimenCollectionProcedureCode("Specimen collection"),
            datetime.datetime(2023, 8, 5),
            "Extracted",
        ),
        AnatomicPathologySpecimenTypesCode("tissue specimen"),
        [
            Fixation(
                SpecimenFixativesCode("Neutral Buffered Formalin"),
                datetime.datetime(2023, 8, 5),
            )
        ],
    )

    part_2 = Specimen(
        "part 2",
        Collection(
            SpecimenCollectionProcedureCode("Specimen collection"),
            datetime.datetime(2023, 8, 5),
            "Extracted",
        ),
        AnatomicPathologySpecimenTypesCode("tissue specimen"),
        [
            Fixation(
                SpecimenFixativesCode("Neutral Buffered Formalin"),
                datetime.datetime(2023, 8, 5),
            )
        ],
    )

    block = Sample(
        "block 1",
        [
            part_1.sample(
                SpecimenSamplingProcedureCode("Dissection"),
                datetime.datetime(2023, 8, 5),
                "Sampling to block",
            ),
            part_2.sample(
                SpecimenSamplingProcedureCode("Dissection"),
                datetime.datetime(2023, 8, 5),
                "Sampling to block",
            ),
        ],
        AnatomicPathologySpecimenTypesCode("tissue specimen"),
        [
            Embedding(
                SpecimenEmbeddingMediaCode("Paraffin wax"),
                datetime.datetime(2023, 8, 5),
            )
        ],
    )

    sample_1 = SlideSample(
        "Sample 1",
        [Code("value", "schema", "meaning")],
        block.sample(
            SpecimenSamplingProcedureCode("Block sectioning"),
            datetime.datetime(2023, 8, 5),
            "Sampling to slide",
            [part_1.samplings[0]],
        ),
        UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"),
        localization=SampleLocalization(
            x=Measurement(0, UnitCode("mm")),
            y=Measurement(0, UnitCode("mm")),
        ),
    )

    sample_2 = SlideSample(
        "Sample 2",
        [Code("value", "schema", "meaning")],
        block.sample(
            SpecimenSamplingProcedureCode("Block sectioning"),
            datetime.datetime(2023, 8, 5),
            "Sampling to slide",
            [part_2.samplings[0]],
        ),
        UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445424"),
        localization=SampleLocalization(
            x=Measurement(10, UnitCode("mm")),
            y=Measurement(0, UnitCode("mm")),
        ),
    )

    stainings = [
        Staining(
            [
                SpecimenStainsCode("hematoxylin stain"),
                SpecimenStainsCode("water soluble eosin stain"),
            ],
            date_time=datetime.datetime(2023, 8, 5),
        ),
    ]

    yield Slide(identifier="Slide 1", stainings=stainings, samples=[sample_1, sample_2])


@pytest.fixture()
def series():
    yield Series(
        UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"), 1
    )


@pytest.fixture()
def study():
    yield Study(
        UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"),
        "identifier",
        datetime.date(2023, 8, 5),
        datetime.time(12, 3),
        "accession number",
        "referring physician name",
    )


@pytest.fixture()
def pyramid(image: Image, optical_path: OpticalPath):
    yield Pyramid(image=image, optical_paths=[optical_path])


@pytest.fixture()
def wsi_metadata(
    study: Study,
    series: Series,
    patient: Patient,
    equipment: Equipment,
    pyramid: Pyramid,
    slide: Slide,
    label: Label,
):
    yield WsiMetadata(
        study=study,
        series=series,
        patient=patient,
        equipment=equipment,
        pyramid=pyramid,
        slide=slide,
        label=label,
    )
