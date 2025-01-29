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

import os
import platform
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict

import pytest
from pydicom.uid import JPEG2000, UID
from wsidicom import WsiDicom
from wsidicom.codec.encoder import Jpeg2kEncoder, Jpeg2kSettings

from wsidicomizer.wsidicomizer import WsiDicomizer

DEFAULT_TILE_SIZE = 512

test_parameters = {
    "svs": {
        "CMU-1/CMU-1.svs": {
            "convert": True,
            "openslide": True,
            "include_levels": [0, 1, 2],
            "lowest_included_pyramid_level": 0,
            "photometric_interpretation": "RGB",
            "image_coordinate_system": {"x": 25.691574, "y": 23.449873},
            "icc_profile": True,
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
            "openslide": True,
            "include_levels": [0, 1, 2],
            "lowest_included_pyramid_level": 0,
            "photometric_interpretation": "RGB",
            "image_coordinate_system": {"x": 18.34152, "y": 22.716894},
            "icc_profile": True,
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
            "openslide": False,
            "include_levels": [0],
            "lowest_included_pyramid_level": 0,
            "tile_size": 512,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "icc_profile": False,
            "read_region": [
                {
                    "location": {"x": 30000, "y": 30000},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "aa9e76930398facc8c7910e053a7f418",
                },
                {
                    "location": {"x": 30720, "y": 25600},
                    "level": 0,
                    "size": {"width": 512, "height": 512},
                    "md5": "ac145933f80f64abac8d69eeb2ea537b",
                },
            ],
            "read_region_openslide": [],
            "read_thumbnail": [],
        }
    },
    "mirax": {
        "CMU-1/CMU-1.mrxs": {
            "convert": True,
            "openslide": True,
            "include_levels": [4, 6],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "encode_format": "jpeg2000",
            "encode_quality": 0,
            "photometric_interpretation": "YBR_ICT",
            "image_coordinate_system": {"x": 2.3061675, "y": 20.79015},
            "icc_profile": False,
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
            "openslide": True,
            "include_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "icc_profile": False,
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
            "openslide": True,
            "include_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "icc_profile": False,
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
            "openslide": True,
            "include_levels": [4, 5, 6],
            "lowest_included_pyramid_level": 4,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "icc_profile": False,
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
    "isyntax": {
        "isyntax1/testslide.isyntax": {
            "convert": False,
            "openslide": False,
            "include_levels": [0],
            "lowest_included_pyramid_level": 0,
            "photometric_interpretation": "YBR_FULL_422",
            "image_coordinate_system": {"x": 0.0, "y": 0.0},
            "icc_profile": True,
            "read_region": [
                {
                    "location": {"x": 18000, "y": 39000},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "47d0eea527c6203817350a5b38c34a85",
                },
                {
                    "location": {"x": 20000, "y": 40000},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "3690f9decbd78ef83ed0b5c949050a15",
                },
                {
                    "location": {"x": 20500, "y": 40300},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "md5": "abb552d51b81feaf0768067708b1c169",
                },
            ],
            "read_thumbnail": [],
            "read_region_openslide": [],
            "skip_hash_test_platforms": ["Darwin"],
        }
    },
}


class Jpeg2kTestEncoder(Jpeg2kEncoder):
    """Jpeg 2000 encoder used for testing.
    Pretends to be lossy but encodes losslessly so that image data is not changed."""

    def __init__(self):
        settings = Jpeg2kSettings(levels=[0])
        super().__init__(settings)

    @property
    def lossy(self) -> bool:
        return True

    @property
    def transfer_syntax(self) -> UID:
        return JPEG2000

    @property
    def photometric_interpretation(self) -> str:
        return "YBR_ICT"


def convert_wsi(file_path: Path, file_parameters: Dict[str, Any]):
    include_levels = file_parameters["include_levels"]
    tile_size = file_parameters.get("tile_size", DEFAULT_TILE_SIZE)
    tempdir = TemporaryDirectory()
    WsiDicomizer.convert(
        file_path,
        output_path=tempdir.name,
        tile_size=tile_size,
        include_levels=include_levels,
        encoding=Jpeg2kTestEncoder(),
    )
    return tempdir


@pytest.fixture(scope="module")
def icc_profile():
    yield bytes([0x00, 0x01, 0x02, 0x03])


@pytest.fixture(scope="module")
def testdata_dir():
    yield Path(os.environ.get("WSIDICOMIZER_TESTDIR", "tests/testdata"))


@pytest.fixture(scope="module")
def wsi_files(testdata_dir: Path):
    return {
        file_format: {
            file: testdata_dir.joinpath("slides", file_format, file)
            for file in file_format_parameters
        }
        for file_format, file_format_parameters in test_parameters.items()
        if platform.system()
        not in file_format_parameters.get("skip_hash_test_platforms", [])
    }


@pytest.fixture(scope="module")
def converted(wsi_files: Dict[str, Dict[str, Path]]):
    converted_folders = {
        file_format: {
            file: convert_wsi(wsi_files[file_format][file], file_parameters)
            for file, file_parameters in file_format_parameters.items()
            if wsi_files[file_format][file].exists() and file_parameters["convert"]
        }
        for file_format, file_format_parameters in test_parameters.items()
        if platform.system()
        not in file_format_parameters.get("skip_hash_test_platforms", [])
    }
    yield converted_folders
    for file_format in converted_folders.values():
        for converted_folder in file_format.values():
            try:
                converted_folder.cleanup()
            except Exception as exception:
                raise Exception("Failed to cleanup", converted_folder) from exception


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
            if file_format not in converted or file not in converted[file_format]:
                wsi = WsiDicomizer.open(file_path)
            else:
                wsi = WsiDicom.open(converted[file_format][file].name)
            wsis[file_format][file] = wsi
    yield wsis
    for file_format in wsis.values():
        for wsi in file_format.values():
            wsi.close()


@pytest.fixture(scope="module")
def converted_path(
    converted: Dict[str, Dict[str, TemporaryDirectory]], file_format: str, file: str
):
    if file_format not in converted or file not in converted[file_format]:
        pytest.skip(f"Skipping {file_format} {file} due to missing file.")
    yield converted[file_format][file]


@pytest.fixture(scope="module")
def wsi(
    wsis: Dict[str, Dict[str, WsiDicom]],
    file_format: str,
    file: str,
):
    if file_format not in wsis or file not in wsis[file_format]:
        pytest.skip(f"Skipping {file_format} {file} due to missing file.")
    yield wsis[file_format][file]


@pytest.fixture(scope="module")
def wsi_file(
    wsi_files: Dict[str, Dict[str, Path]],
    file_format: str,
    file: str,
):
    if file_format not in wsi_files or file not in wsi_files[file_format]:
        pytest.skip(f"Skipping {file_format} {file} due to no test parameters.")
    filepath = wsi_files[file_format][file]
    if not filepath.exists():
        pytest.skip(f"Skipping {file_format} {file} due to missing file.")
    yield filepath
