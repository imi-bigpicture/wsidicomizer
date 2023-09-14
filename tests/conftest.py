import datetime
import os
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Sequence

import pytest
from pydicom.sr.coding import Code
from pydicom.uid import UID
from wsidicom import WsiDicom
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
)

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
from wsidicomizer.metadata.equipment import Equipment
from wsidicomizer.metadata.image import (
    ExtendedDepthOfField,
    FocusMethod,
    Image,
    ImageCoordinateSystem,
)
from wsidicomizer.metadata.label import Label
from wsidicomizer.metadata.sample import (
    Collection,
    Embedding,
    ExtractedSpecimen,
    Fixation,
    Processing,
    Sample,
    SampledSpecimen,
    SlideSample,
    SlideSamplePosition,
    Staining,
)
from wsidicomizer.metadata.slide import Slide
from wsidicomizer.wsidicomizer import WsiDicomizer

DEFAULT_TILE_SIZE = 512

test_parameters = {
    "svs": {
        "CMU-1/CMU-1.svs": {
            "convert": True,
            "include_levels": [0, 1, 2],
            "lowest_included_pyramid_level": 0,
            "photometric_interpretation": "RGB",
            "image_coordinate_system": {"x": 25.691574, "y": 23.449873},
            "read_region": [
                {
                    "location": {"x": 900, "y": 1200},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "md5": "ee6fc53c821ed39eb8bb9ea31d6065eb",
                },
                {
                    "location": {"x": 450, "y": 600},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "md5": "90d96fafc102df44225b6073e6cd4e3b",
                },
                {
                    "location": {"x": 225, "y": 300},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "md5": "2225853ad4952b9f1854f9cb97c6736b",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 16400, "y": 21200},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "51cc84bd6c1c71a7a7c3e736b3bd3970",
                }
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "b27df8f554f6bdd4d4fa42d67eeebe6e",
                }
            ],
        },
        "svs1/input.svs": {
            "convert": True,
            "include_levels": [0, 1, 2],
            "lowest_included_pyramid_level": 0,
            "photometric_interpretation": "RGB",
            "image_coordinate_system": {"x": 18.34152, "y": 22.716894},
            "read_region": [
                {
                    "location": {"x": 500, "y": 500},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "md5": "b5dae0fce9692bdbb1ab2799d7874402",
                },
                {
                    "location": {"x": 0, "y": 0},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "md5": "b08559b881da13a6c0fb218c44244951",
                },
                {
                    "location": {"x": 100, "y": 100},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "md5": "51cc84bd6c1c71a7a7c3e736b3bd3970",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 8000, "y": 8000},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "51cc84bd6c1c71a7a7c3e736b3bd3970",
                },
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "379210d2aee83bb590aa2a4223707ac1",
                }
            ],
        },
    },
    "czi": {
        "czi1/input.czi": {
            "convert": False,
            "include_levels": [0],
            "lowest_included_pyramid_level": 0,
            "tile_size": 512,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "read_region": [
                {
                    "location": {"x": 30000, "y": 30000},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "aa9e76930398facc8c7910e053a7f418",
                }
            ],
            "read_region_openslide": [],
            "read_thumbnail": [],
        }
    },
    "mirax": {
        "CMU-1/CMU-1.mrxs": {
            "convert": True,
            "include_levels": [4, 6],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "encode_format": "jpeg2000",
            "encode_quality": 0,
            "photometric_interpretation": "YBR_RCT",
            "image_coordinate_system": {"x": 2.3061675, "y": 20.79015},
            "read_region": [
                # OpenSlide produces different results across platforms
                # {
                #     "location": {
                #         "x": 50,
                #         "y": 100
                #     },
                #     "level": 6,
                #     "size": {
                #         "width": 500,
                #         "height": 500
                #     },
                #     "md5": "fe29e76f5904d65253d8eb742b244789"
                # },
                # {
                #     "location": {
                #         "x": 400,
                #         "y": 500
                #     },
                #     "level": 4,
                #     "size": {
                #         "width": 500,
                #         "height": 500
                #     },
                #     "md5": "4f4c904ed9257e385fc8f0818337d9e7"
                # }
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 50, "y": 100},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                },
                {
                    "location": {"x": 400, "y": 500},
                    "level": 4,
                    "size": {"width": 500, "height": 500},
                },
            ],
            "read_thumbnail": [],
        }
    },
    "ndpi": {
        "CMU-1/CMU-1.ndpi": {
            "convert": True,
            "include_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "read_region": [
                {
                    "location": {"x": 940, "y": 1500},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "md5": "d0c6f57e80b8a05e5617049d1e880425",
                },
                {
                    "location": {"x": 470, "y": 750},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "md5": "705072936f3171e04d22e82a36340250",
                },
                {
                    "location": {"x": 235, "y": 375},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "md5": "29949c1bbf444113b8f07d0ba454b25e",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 940, "y": 1500},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                },
                {
                    "location": {"x": 235, "y": 375},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                },
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "ea87500dc544f45c6f600811138dad23",
                }
            ],
        },
        "ndpi1/input.ndpi": {
            "convert": True,
            "include_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "read_region": [
                {
                    "location": {"x": 0, "y": 0},
                    "level": 8,
                    "size": {"width": 200, "height": 200},
                    "md5": "3053d9c4e6fe5b77ce1ac72788e1c5ee",
                },
                {
                    "location": {"x": 100, "y": 100},
                    "level": 8,
                    "size": {"width": 200, "height": 200},
                    "md5": "a435e9806ba8a9a8227ebbb99728235c",
                },
                {
                    "location": {"x": 0, "y": 0},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                    "md5": "15f166e1facb38aba2eb47f7622c5c3c",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 0, "y": 0},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                }
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "995791915459762ac1c251fc8351b4f6",
                }
            ],
        },
        # "ndpi2/input.ndpi": {
        #     "convert": True,
        #     "include_levels": [4, 6],
        #     "lowest_included_pyramid_level": 4,
        #     "tile_size": 1024,
        #     "photometric_interpretation": "YBR_FULL_422",
        #     "image_coordinate_system": {
        #         "x": 0.0,
        #         "y": 0.0
        #     },
        #     "read_region": [
        #         {
        #             "location": {
        #                 "x": 3000,
        #                 "y": 3000
        #             },
        #             "level": 4,
        #             "size": {
        #                 "width": 500,
        #                 "height": 500
        #             },
        #             "md5": "fee89f955ed08550391b59cdff4a7aef"
        #         },
        #         {
        #             "location": {
        #                 "x": 1000,
        #                 "y": 1000
        #             },
        #             "level": 6,
        #             "size": {
        #                 "width": 500,
        #                 "height": 500
        #             },
        #             "md5": "59afbe85473f23038e97ee40213862b4"
        #         }
        #     ],
        #     "read_region_openslide": [
        #         {
        #             "location": {
        #                 "x": 3000,
        #                 "y": 3000
        #             },
        #             "level": 4,
        #             "size": {
        #                 "width": 500,
        #                 "height": 500
        #             },
        #         },
        #         {
        #             "location": {
        #                 "x": 1000,
        #                 "y": 1000
        #             },
        #             "level": 6,
        #             "size": {
        #                 "width": 500,
        #                 "height": 500
        #             },
        #         }
        #     ],
        #     "read_thumbnail": [
        #         {
        #             "size": {
        #                 "width": 512,
        #                 "height": 512
        #             },
        #             "md5": "701961c4afcf42d545e30ad8346fc8f4"
        #         }
        #     ]
        # }
    },
    "philips_tiff": {
        "philips1/input.tif": {
            "convert": True,
            "include_levels": [4, 5, 6],
            "lowest_included_pyramid_level": 4,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "read_region": [
                {
                    "location": {"x": 500, "y": 1000},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "md5": "38d562c38a21c503dd1da6faff8ac129",
                },
                {
                    "location": {"x": 150, "y": 300},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "md5": "faa48eb511e39271dd222a89ef853c76",
                },
                {
                    "location": {"x": 1000, "y": 2000},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "md5": "b35b1013f4009ce11f29b82a52444191",
                },
            ],
            "read_region_openslide": [
                {
                    "location": {"x": 500, "y": 1000},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                },
                {
                    "location": {"x": 150, "y": 300},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                },
                {
                    "location": {"x": 1000, "y": 2000},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                },
            ],
            "read_thumbnail": [
                {
                    "size": {"width": 512, "height": 512},
                    "md5": "922ab1407d79de6b117bc561625f1a49",
                }
            ],
        }
    },
}


@pytest.fixture(scope="module")
def testdata_dir():
    yield Path(os.environ.get("WSIDICOMIZER_TESTDIR", "tests/testdata"))


@pytest.fixture(scope="module")
def wsi_files(testdata_dir: Path):
    files: Dict[str, Dict[str, Path]] = defaultdict(dict)
    for file_format, file_format_parameters in test_parameters.items():
        for file in file_format_parameters:
            files[file_format][file] = testdata_dir.joinpath(
                "slides", file_format, file
            )
    return files


@pytest.fixture(scope="module")
def converted(
    wsi_files: Dict[str, Dict[str, Path]],
):
    converted_folders: Dict[str, Dict[str, TemporaryDirectory]] = defaultdict(dict)
    for file_format, file_format_parameters in test_parameters.items():
        for file, file_parameters in file_format_parameters.items():
            file_path = wsi_files[file_format][file]
            if not file_path.exists() or not file_parameters["convert"]:
                continue
            include_levels = file_parameters["include_levels"]
            tile_size = file_parameters.get("tile_size", DEFAULT_TILE_SIZE)
            tempdir = TemporaryDirectory()
            WsiDicomizer.convert(
                file_path,
                output_path=str(tempdir.name),
                tile_size=tile_size,
                include_levels=include_levels,
                encoding_format="jpeg2000",
                encoding_quality=0,
            )
            converted_folders[file_format][file] = tempdir
    yield converted_folders
    for file_format in converted_folders.values():
        for converted_folder in file_format.values():
            converted_folder.cleanup()


@pytest.fixture(scope="module")
def wsis(
    wsi_files: Dict[str, Dict[str, Path]],
    converted: Dict[str, Dict[str, TemporaryDirectory]],
):
    wsis: Dict[str, Dict[str, WsiDicom]] = defaultdict(dict)
    for file_format, file_format_parameters in wsi_files.items():
        for file, file_path in file_format_parameters.items():
            if not file_path.exists():
                continue
            if not file_format in converted or file not in converted[file_format]:
                wsi = WsiDicomizer.open(file_path)
            else:
                wsi = WsiDicom.open(converted[file_format][file].name)
            wsis[file_format][file] = wsi
    yield wsis
    for file_format in wsis.values():
        for wsi in file_format.values():
            wsi.close()


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
    # image_coordinate_system = ImageCoordinateSystem(PointMm(20.0, 30.0), 90.0)
    # extended_depth_of_field = ExtendedDepthOfField(5, 0.5)
    yield Image(
        acquisition_datetime,
        focus_method,
        extended_depth_of_field,
        image_coordinate_system
        # datetime.datetime(2023, 8, 5),
        # FocusMethod.AUTO,
        # extended_depth_of_field,
        # image_coordinate_system,
    )


@pytest.fixture()
def label():
    yield Label("label_text", "barcode_value", True, True, False)


@pytest.fixture(params=[IlluminationColorCode("Full Spectrum"), 400.0])
def optical_path(request):
    illumination = request.param
    assert isinstance(illumination, (IlluminationColorCode, float))
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
    yield OpticalPath(
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
    yield ExtractedSpecimen(
        "specimen", AnatomicPathologySpecimenTypesCode("Gross specimen"), collection
    )


@pytest.fixture()
def sample(extracted_specimen: ExtractedSpecimen):
    processing = Processing(
        SpecimenPreparationStepsCode("Specimen clearing"),
        datetime.datetime(2023, 8, 5),
    )
    yield Sample(
        "sample",
        AnatomicPathologySpecimenTypesCode("Tissue section"),
        [
            extracted_specimen.sample(
                SpecimenSamplingProcedureCode("Dissection"),
                datetime.datetime(2023, 8, 5),
                "Sampling to block",
            ),
        ],
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
        position="left",
    )


@pytest.fixture()
def slide():
    part_1 = ExtractedSpecimen(
        "part 1",
        AnatomicPathologySpecimenTypesCode("tissue specimen"),
        Collection(
            SpecimenCollectionProcedureCode("Specimen collection"),
            datetime.datetime(2023, 8, 5),
            "Extracted",
        ),
        [
            Fixation(
                SpecimenFixativesCode("Neutral Buffered Formalin"),
                datetime.datetime(2023, 8, 5),
            )
        ],
    )

    part_2 = ExtractedSpecimen(
        "part 2",
        AnatomicPathologySpecimenTypesCode("tissue specimen"),
        Collection(
            SpecimenCollectionProcedureCode("Specimen collection"),
            datetime.datetime(2023, 8, 5),
            "Extracted",
        ),
        [
            Fixation(
                SpecimenFixativesCode("Neutral Buffered Formalin"),
                datetime.datetime(2023, 8, 5),
            )
        ],
    )

    block = Sample(
        "block 1",
        AnatomicPathologySpecimenTypesCode("tissue specimen"),
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
        SlideSamplePosition(0, 0, 0),
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
        position=SlideSamplePosition(10, 0, 0),
    )

    stains = [
        Staining(
            [
                SpecimenStainsCode("hematoxylin stain"),
                SpecimenStainsCode("water soluble eosin stain"),
            ],
        ),
    ]

    yield Slide(identifier="Slide 1", stains=stains, samples=[sample_1, sample_2])


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
