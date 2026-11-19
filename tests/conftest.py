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

import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from opentile.geometry import Point as OpenTilePoint
from opentile.geometry import Region as OpenTileRegion
from opentile.geometry import Size as OpenTileSize
from pydicom.uid import JPEG2000, UID, JPEGBaseline8Bit
from upath import UPath
from wsidicom import WsiDicom
from wsidicom.codec.encoder import Encoder, Jpeg2kEncoder, Jpeg2kSettings

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.wsidicomizer import SourceIdentifier, WsiDicomizer

DEFAULT_TILE_SIZE = 512
# Least PSNR (dB) between thumbnails generated from different sources' pyramids:
# about an RMS difference of 4 (lowest measured is 39.4 dB, philips1).
PSNR_MIN_THUMBNAIL = 36.0

# Expectations per test file. File-level keys hold what every source reading the
# file must agree on (and the conversion inputs). Keys under `sources` hold what
# depends on the source (SourceIdentifier value) reading the file, and overlay the
# file-level ones for that source; tests run once per listed source. `agreement`
# cases compare a source's converted output to another source reading the original
# file directly, within `min_psnr` (dB; inf requires identical pixels).
test_parameters = {
    "svs": {
        "CMU-1/CMU-1.svs": {
            "convert": True,
            "has_overview": True,
            "convert_levels": None,
            "lowest_included_pyramid_level": 0,
            "image_coordinate_system": {"x": 25, "y": 50, "rotation": 180},
            "icc_profile": True,
            "embedded_thumbnail_size": (1024, 732),
            "thumbnail_pixel_spacing": (0.022416015625, 0.022416015625),
            "imaged_size": (22.954000473022461, 16.42408561706543),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "RGB",
                    "transfer_syntax": JPEGBaseline8Bit,
                    "passthrough": True,
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
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "b27df8f554f6bdd4d4fa42d67eeebe6e",
                        }
                    ],
                    "pixel_spacings": [
                        (0.000499, 0.000499),
                        (0.001996, 0.001996),
                        (0.007984, 0.007984),
                    ],
                    "focal_planes": [0.0],
                }
            },
            "agreement": [
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 16400, "y": 21200},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "thumbnail": {"width": 512, "height": 512},
                    "min_psnr": PSNR_MIN_THUMBNAIL,
                },
            ],
        },
        "JP2K-33003-1/JP2K-33003-1.svs": {
            "convert": True,
            "has_overview": True,
            "convert_levels": None,
            "lowest_included_pyramid_level": 0,
            "image_coordinate_system": {"x": 25, "y": 50, "rotation": 180},
            "icc_profile": True,
            "skip_hash_test_platforms": ["Darwin"],
            "embedded_thumbnail_size": (674, 768),
            "thumbnail_pixel_spacing": (0.00569796023739, 0.00569796023739),
            "imaged_size": (3.8404252529144287, 4.370750427246094),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
                    "transfer_syntax": JPEG2000,
                    "passthrough": True,
                    "read_region": [
                        {
                            "location": {"x": 0, "y": 0},
                            "level": 0,
                            "size": {"width": 200, "height": 200},
                            "md5": "59e3ed51eba8344291349fd714e88df5",
                        },
                        {
                            "location": {"x": 0, "y": 0},
                            "level": 1,
                            "size": {"width": 200, "height": 200},
                            "md5": "f1c1962496298e5b92dff48a885fcd55",
                        },
                        {
                            "location": {"x": 0, "y": 0},
                            "level": 2,
                            "size": {"width": 200, "height": 200},
                            "md5": "a558d7078c9e977bdb0f473335ad3851",
                        },
                    ],
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "809b85697e43b71c2b2ba77a777b91f1",
                        }
                    ],
                    "pixel_spacings": [
                        (0.0002498, 0.0002498),
                        (0.00099933000260, 0.00099933000260),
                        (0.00199918021864, 0.00199918021864),
                    ],
                    "focal_planes": [0.0],
                }
            },
        },
        "CMU-1-JP2K-33005/CMU-1-JP2K-33005.svs": {
            "convert": True,
            "has_overview": True,
            "convert_levels": None,
            "lowest_included_pyramid_level": 0,
            "image_coordinate_system": {"x": 25, "y": 50, "rotation": 180},
            "icc_profile": True,
            "skip_hash_test_platforms": ["Darwin"],
            "embedded_thumbnail_size": (1024, 732),
            "thumbnail_pixel_spacing": (0.022416015625, 0.022416015625),
            "imaged_size": (22.95400047302246, 16.413606643676758),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "YBR_ICT",
                    "transfer_syntax": JPEG2000,
                    "passthrough": True,
                    "read_region": [
                        {
                            "location": {"x": 0, "y": 0},
                            "level": 0,
                            "size": {"width": 200, "height": 200},
                            "md5": "94bced3d9d84f51b5c953dfb1e9cd495",
                        },
                        {
                            "location": {"x": 0, "y": 0},
                            "level": 1,
                            "size": {"width": 200, "height": 200},
                            "md5": "44ceca50920e864c665ac54adf01a981",
                        },
                        {
                            "location": {"x": 0, "y": 0},
                            "level": 2,
                            "size": {"width": 200, "height": 200},
                            "md5": "acb6dcf3afecde42a6d4f9d707f254c8",
                        },
                    ],
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "e9ab4d977293f7739aee97e9ee615cbd",
                        }
                    ],
                    "pixel_spacings": [
                        (0.000499, 0.000499),
                        (0.001996, 0.001996),
                        (0.007984, 0.007984),
                    ],
                    "focal_planes": [0.0],
                }
            },
        },
        "svs1/input.svs": {
            "convert": True,
            "has_overview": True,
            "convert_levels": None,
            "lowest_included_pyramid_level": 0,
            "image_coordinate_system": {"x": 25, "y": 50, "rotation": 180},
            "icc_profile": True,
            "embedded_thumbnail_size": (1024, 753),
            "thumbnail_pixel_spacing": (0.0230818171875, 0.0230818171875),
            "imaged_size": (23.635780334472656, 17.396451950073242),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "RGB",
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
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "379210d2aee83bb590aa2a4223707ac1",
                        }
                    ],
                    "pixel_spacings": [
                        (0.0004944, 0.0004944),
                        (0.00197772410677, 0.00197772410677),
                        (0.00791288275862, 0.00791288275862),
                    ],
                    "focal_planes": [0.0],
                }
            },
            "agreement": [
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 8000, "y": 8000},
                    "level": 0,
                    "size": {"width": 200, "height": 200},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "thumbnail": {"width": 512, "height": 512},
                    "min_psnr": PSNR_MIN_THUMBNAIL,
                },
            ],
        },
        "zstack1/zstack1.svs": {
            "convert": True,
            "has_overview": True,
            "convert_levels": [0, 1],
            "lowest_included_pyramid_level": 0,
            "image_coordinate_system": {"x": 25, "y": 50, "rotation": 180},
            "icc_profile": True,
            "embedded_thumbnail_size": (926, 768),
            "thumbnail_pixel_spacing": (0.00541937375810, 0.00541937375810),
            "imaged_size": (5.018340110778809, 4.158686637878418),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "RGB",
                    "read_region": [
                        {
                            "location": {"x": 400, "y": 400},
                            "level": 2,
                            "z": 0,
                            "size": {"width": 500, "height": 500},
                            "md5": "ad7816bc826597787fb65a29cb2fe087",
                        },
                        {
                            "location": {"x": 400, "y": 400},
                            "level": 2,
                            "z": 0.9,
                            "size": {"width": 500, "height": 500},
                            "md5": "e76a5e0f969dd188a7d2c9421de391a8",
                        },
                    ],
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "a9b7865911ba2436e5a3eecae09ef5ad",
                        }
                    ],
                    "pixel_spacings": [
                        (0.0005039, 0.0005039),
                        (0.00201620735235, 0.00201620735235),
                    ],
                    "focal_planes": [0.0, 0.9, 1.8, 2.7, 3.6, 4.5, 5.4],
                }
            },
        },
    },
    "czi": {
        "czi1/input.czi": {
            "convert": False,
            "has_overview": False,
            "convert_levels": [0],
            "lowest_included_pyramid_level": 0,
            "tile_size": 512,
            "image_coordinate_system": {"x": 0.0, "y": 0.0, "rotation": 0},
            "icc_profile": False,
            "embedded_thumbnail_size": None,
            "thumbnail_pixel_spacing": None,
            "imaged_size": (15.28164, 11.896279999999999),
            "sources": {
                "czi": {
                    "has_label": False,
                    "photometric_interpretation": "YBR_FULL_422",
                    "transfer_syntax": JPEGBaseline8Bit,
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
                    "read_thumbnail": [],
                    "pixel_spacings": [
                        (0.00021999999999999998, 0.00021999999999999998)
                    ],
                    "focal_planes": [0.0],
                }
            },
        }
    },
    "mirax": {
        "CMU-1/CMU-1.mrxs": {
            "convert": True,
            "has_overview": True,
            "convert_levels": [4, 6],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "encode_format": "jpeg2000",
            "encode_quality": 0,
            "image_coordinate_system": {"x": 2.3061675, "y": 20.79015, "rotation": 270},
            "icc_profile": False,
            "skip_hash_test_platforms": ["Darwin"],
            "embedded_thumbnail_size": (534, 742),
            "thumbnail_pixel_spacing": (0.02974039812646, 0.02974039812646),
            "imaged_size": (15.883237838745117, 22.080989837646484),
            "sources": {
                "openslide": {
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
                    "read_region": [
                        {
                            "location": {"x": 50, "y": 100},
                            "level": 6,
                            "size": {"width": 500, "height": 500},
                            "md5": "b9052fc1ebbe99582906c575511fe944",
                        },
                        {
                            "location": {"x": 400, "y": 500},
                            "level": 4,
                            "size": {"width": 500, "height": 500},
                            "md5": "a11881460a4fae78ddfef1100339cac0",
                        },
                    ],
                    "read_thumbnail": [],
                    "pixel_spacings": [(0.00372, 0.00372), (0.01488, 0.01488)],
                    "focal_planes": [0.0],
                },
                "mirax": {
                    # only the base level is read; the pyramid is built from it
                    "convert_levels": None,
                    "lowest_included_pyramid_level": 0,
                    "pixel_spacings": [
                        (0.0002325, 0.0002325),
                        (0.000465, 0.000465),
                        (0.00093, 0.00093),
                        (0.00186, 0.00186),
                        (0.00372, 0.00372),
                        (0.00744, 0.00744),
                        (0.01488, 0.01488),
                        (0.02976, 0.02976),
                    ],
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
                    "read_region": [
                        {
                            "location": {"x": 50, "y": 100},
                            "level": 6,
                            "size": {"width": 500, "height": 500},
                            "md5": "227a98c8ee2fa94e5ef5058007f81c39",
                        },
                        {
                            "location": {"x": 400, "y": 500},
                            "level": 4,
                            "size": {"width": 500, "height": 500},
                            "md5": "b5ba3b652194e454a4f188c87ef87477",
                        },
                    ],
                    "read_thumbnail": [],
                    "focal_planes": [0.0],
                },
            },
            # The native reader builds its pyramid from the base level, openslide
            # reads the stored levels (blurrier, composed from other photos).
            "agreement": [
                {
                    "converted": "mirax",
                    "reference": "openslide",
                    "location": {"x": 15360, "y": 40448},
                    "level": 0,
                    "size": {"width": 500, "height": 500},
                    "min_psnr": math.inf,
                },
                {
                    # spans three vertical photo seams; a paste order by placed
                    # position takes the other photo at two of them
                    "converted": "mirax",
                    "reference": "openslide",
                    "location": {"x": 19700, "y": 23743},
                    "level": 0,
                    "size": {"width": 2800, "height": 512},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "mirax",
                    "reference": "openslide",
                    "location": {"x": 50, "y": 100},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                    "min_psnr": 29.0,
                },
                {
                    "converted": "mirax",
                    "reference": "openslide",
                    "location": {"x": 400, "y": 500},
                    "level": 4,
                    "size": {"width": 500, "height": 500},
                    "min_psnr": 27.0,
                },
                {
                    "converted": "openslide",
                    "reference": "openslide",
                    "location": {"x": 50, "y": 100},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "openslide",
                    "reference": "openslide",
                    "location": {"x": 400, "y": 500},
                    "level": 4,
                    "size": {"width": 500, "height": 500},
                    "min_psnr": math.inf,
                },
            ],
        }
    },
    "ndpi": {
        "CMU-1/CMU-1.ndpi": {
            "convert": True,
            "has_overview": True,
            "convert_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "image_coordinate_system": {"x": 23.519, "y": 44.307, "rotation": 180},
            "icc_profile": False,
            "embedded_thumbnail_size": None,
            "thumbnail_pixel_spacing": None,
            "imaged_size": (23.368324279785156, 17.357906341552734),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
                    "transfer_syntax": JPEGBaseline8Bit,
                    "passthrough": True,
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
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "ea87500dc544f45c6f600811138dad23",
                        }
                    ],
                    "pixel_spacings": [
                        (0.00730460189920, 0.00728332119446),
                        (0.02923976608187, 0.02915451895044),
                    ],
                    "focal_planes": [0.0],
                }
            },
            "agreement": [
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 940, "y": 1500},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 235, "y": 375},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "thumbnail": {"width": 512, "height": 512},
                    "min_psnr": PSNR_MIN_THUMBNAIL,
                },
            ],
        },
        "ndpi1/input.ndpi": {
            "convert": True,
            "has_overview": True,
            "convert_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "image_coordinate_system": {"x": 23.393, "y": 32.103, "rotation": 180},
            "icc_profile": False,
            "embedded_thumbnail_size": None,
            "thumbnail_pixel_spacing": None,
            "imaged_size": (28.697086334228516, 19.497819900512695),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
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
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "995791915459762ac1c251fc8351b4f6",
                        }
                    ],
                    "pixel_spacings": [
                        (0.00361663652803, 0.00361663652803),
                        (0.01447178002894, 0.01447178002894),
                    ],
                    "focal_planes": [0.0],
                }
            },
            "agreement": [
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 0, "y": 0},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "thumbnail": {"width": 512, "height": 512},
                    "min_psnr": PSNR_MIN_THUMBNAIL,
                },
            ],
        },
        "ndpi2/input.ndpi": {
            "convert": True,
            "has_overview": True,
            "convert_levels": [4, 6],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "image_coordinate_system": {"x": 23.563, "y": 38.715, "rotation": 180},
            "icc_profile": False,
            "embedded_thumbnail_size": None,
            "thumbnail_pixel_spacing": None,
            "imaged_size": (36.21491622924805, 23.563446044921875),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
                    "read_region": [
                        {
                            "location": {"x": 1000, "y": 1000},
                            "level": 6,
                            "size": {"width": 500, "height": 500},
                            "md5": "59afbe85473f23038e97ee40213862b4",
                        },
                    ],
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "701961c4afcf42d545e30ad8346fc8f4",
                        }
                    ],
                    "pixel_spacings": [
                        (0.00362844702467, 0.00362844702467),
                        (0.01451378809869, 0.01451378809869),
                    ],
                    "focal_planes": [0.0],
                }
            },
            "agreement": [
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 1000, "y": 1000},
                    "level": 6,
                    "size": {"width": 500, "height": 500},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "thumbnail": {"width": 512, "height": 512},
                    "min_psnr": PSNR_MIN_THUMBNAIL,
                },
            ],
        },
        "zstack1/zstack1.ndpi": {
            "convert": True,
            "has_overview": True,
            "convert_levels": [2, 3],
            "lowest_included_pyramid_level": 4,
            "tile_size": 1024,
            "image_coordinate_system": {"x": 21.798, "y": 34.254, "rotation": 180},
            "icc_profile": False,
            "embedded_thumbnail_size": None,
            "thumbnail_pixel_spacing": None,
            "imaged_size": (20.36567497253418, 18.97710609436035),
            "sources": {
                "opentile": {
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
                    "read_region": [
                        {
                            "location": {"x": 200, "y": 200},
                            "level": 6,
                            "z": 0,
                            "size": {"width": 500, "height": 500},
                            "md5": "ee318f6a456c957dc5c02a5688e22a4b",
                        },
                        {
                            "location": {"x": 200, "y": 200},
                            "level": 6,
                            "z": 1.2,
                            "size": {"width": 500, "height": 500},
                            "md5": "45fca1a626e6a13cf700ef4e92afbd88",
                        },
                    ],
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "7b3ef58e844e078afdba060330aa3d6f",
                        }
                    ],
                    "pixel_spacings": [
                        (0.00361663652803, 0.00361663652803),
                        (0.01447178002894, 0.01447178002894),
                    ],
                    "focal_planes": [-3.6, -2.4, -1.2, 0.0, 1.2, 2.4, 3.6],
                }
            },
            "agreement": [
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 200, "y": 200},
                    "level": 6,
                    "z": 0,
                    "size": {"width": 500, "height": 500},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "thumbnail": {"width": 512, "height": 512},
                    "min_psnr": PSNR_MIN_THUMBNAIL,
                },
            ],
        },
    },
    "philips_tiff": {
        "philips1/input.tif": {
            "convert": True,
            "has_overview": True,
            "convert_levels": [4, 5, 6],
            "lowest_included_pyramid_level": 4,
            "image_coordinate_system": {"x": 25.0, "y": 50.0, "rotation": 180},
            "icc_profile": False,
            "embedded_thumbnail_size": None,
            "thumbnail_pixel_spacing": None,
            "imaged_size": (18.944000244140625, 23.552000045776367),
            "sources": {
                "opentile": {
                    # Passthrough-capable (native JPEG tiles); no need to re-test
                    # transcoding here, so wrap native tiles instead. Transcoding is
                    # covered by other formats. convert_levels/lowest kept so
                    # pixel_spacings stays unchanged.
                    "force_transcoding": False,
                    "passthrough": True,
                    "transfer_syntax": JPEGBaseline8Bit,
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
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
                    "read_thumbnail": [
                        {
                            "size": {"width": 512, "height": 512},
                            "md5": "922ab1407d79de6b117bc561625f1a49",
                        }
                    ],
                    "pixel_spacings": [(0.004, 0.004), (0.008, 0.008), (0.016, 0.016)],
                    "focal_planes": [0.0],
                }
            },
            "agreement": [
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 500, "y": 1000},
                    "level": 5,
                    "size": {"width": 200, "height": 200},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 150, "y": 300},
                    "level": 6,
                    "size": {"width": 200, "height": 200},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "location": {"x": 1000, "y": 2000},
                    "level": 4,
                    "size": {"width": 200, "height": 200},
                    "min_psnr": math.inf,
                },
                {
                    "converted": "opentile",
                    "reference": "openslide",
                    "thumbnail": {"width": 512, "height": 512},
                    "min_psnr": PSNR_MIN_THUMBNAIL,
                },
            ],
        }
    },
    "isyntax": {
        "isyntax1/testslide.isyntax": {
            "convert": False,
            "has_overview": True,
            "convert_levels": [0],
            "lowest_included_pyramid_level": 0,
            "image_coordinate_system": {"x": 25, "y": 50, "rotation": 180},
            "icc_profile": False,
            "skip_hash_test_platforms": ["Darwin"],
            "embedded_thumbnail_size": None,
            "thumbnail_pixel_spacing": None,
            "imaged_size": (9.3455, 18.305500000000002),
            "sources": {
                "isyntax": {
                    "has_label": True,
                    "photometric_interpretation": "YBR_FULL_422",
                    "transfer_syntax": JPEGBaseline8Bit,
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
                    "pixel_spacings": [(0.00025, 0.00025)],
                    "focal_planes": [0.0],
                }
            },
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


def source_parameters(file_format: str, file: str, source: str) -> dict[str, Any]:
    """Return the expectations for a file read with a source: the file-level
    expectations overlaid with the ones listed for the source.

    Parameters
    ----------
    file_format: str
        Format key in `test_parameters`.
    file: str
        File key in the format.
    source: str
        Source (SourceIdentifier value) listed under the file's `sources`.

    Returns
    -------
    dict[str, Any]
        The merged expectations.
    """
    file_parameters = test_parameters[file_format][file]
    shared = {
        key: value
        for key, value in file_parameters.items()
        if key not in ("sources", "agreement")
    }
    return {**shared, **file_parameters["sources"][source]}


def source_cases() -> list[tuple[str, str, str, dict[str, Any]]]:
    """Return a `(file_format, file, source, parameters)` case for each source
    listed for each test file, with the merged expectations of `source_parameters`.
    """
    return [
        (file_format, file, source, source_parameters(file_format, file, source))
        for file_format, format_files in test_parameters.items()
        for file, file_parameters in format_files.items()
        for source in file_parameters["sources"]
    ]


def agreement_cases() -> list[Any]:
    """Return a `(file_format, file, agreement)` case for each agreement listed for
    each test file, identified by the sources and what they compare."""
    return [
        pytest.param(
            file_format,
            file,
            agreement,
            id=f"{file_format}-{file}-{agreement['converted']}"
            f"-vs-{agreement['reference']}-"
            + (
                "thumbnail"
                if "thumbnail" in agreement
                else f"level{agreement['level']}"
            ),
        )
        for file_format, format_files in test_parameters.items()
        for file, file_parameters in format_files.items()
        for agreement in file_parameters.get("agreement", [])
    ]


def available_source(file_path: Path, source: str) -> SourceIdentifier:
    """Return the identifier of a source, skipping the test if the source is not
    available or does not support the file.

    Parameters
    ----------
    file_path: Path
        File the source should read.
    source: str
        Source (SourceIdentifier value) to read the file with.

    Returns
    -------
    SourceIdentifier
        The identifier to pass as `preferred_source`.
    """
    try:
        identifier = SourceIdentifier(source)
        WsiDicomizer._select_sources(UPath(file_path), identifier)
    except ValueError as exception:  # unknown, or its extra is not installed
        pytest.skip(str(exception))
    except NotImplementedError:
        pytest.skip(f"Source {source} does not support {file_path}.")
    return identifier


def convert_wsi(
    file_path: Path,
    file_parameters: dict[str, Any],
    encoder: Encoder,
    source: SourceIdentifier,
):
    # `convert_levels` (optional, None = all) bounds cost when transcoding. A
    # passthrough-capable format can set `force_transcoding: False` to wrap its native
    # tiles instead of re-encoding, which is cheap enough to convert all levels.
    convert_levels = file_parameters.get("convert_levels")
    force_transcoding = file_parameters.get("force_transcoding", True)
    tile_size = file_parameters.get("tile_size", DEFAULT_TILE_SIZE)
    tempdir = TemporaryDirectory()
    os.rmdir(tempdir.name)
    WsiDicomizer.convert(
        file_path,
        output_path=tempdir.name,
        tile_size=tile_size,
        include_levels=convert_levels,
        encoding=encoder,
        force_transcoding=force_transcoding,
        preferred_source=source,
        # Fixtures describe the levels stored in the file; the default (follow
        # the source's prefer_regenerated_pyramid) is tested separately.
        regenerate_pyramid=False,
    )
    return tempdir


@pytest.fixture
def whole_tile(request: pytest.FixtureRequest) -> OpenTileRegion:
    """The region covering a whole square tile, of the size the test parametrizes
    indirectly."""
    size: int = request.param
    return OpenTileRegion(OpenTilePoint(0, 0), OpenTileSize(size, size))


@pytest.fixture(scope="module")
def icc_profile():
    yield bytes([0x00, 0x01, 0x02, 0x03])


@pytest.fixture(scope="module")
def testdata_dir():
    yield Path(os.environ.get("WSIDICOMIZER_TESTDIR", "tests/testdata")).resolve()


@pytest.fixture(scope="module")
def wsi_files(testdata_dir: Path):
    return {
        file_format: {
            file: testdata_dir.joinpath("slides", file_format, file)
            for file in file_format_parameters
        }
        for file_format, file_format_parameters in test_parameters.items()
    }


@pytest.fixture(scope="module")
def encoder():
    yield Jpeg2kTestEncoder()


@pytest.fixture(scope="module")
def converted(wsi_files: dict[str, dict[str, Path]], encoder: Encoder):
    """Cache of slide conversions, populated lazily on first use by the `wsi` and
    `converted_path` fixtures so only slides whose tests actually run are converted
    (fast-fail; no eager up-front conversion of every file). Cleaned up at module
    teardown."""
    cache: dict[tuple[str, str, str], TemporaryDirectory] = {}
    yield cache
    for converted_folder in cache.values():
        try:
            converted_folder.cleanup()
        except Exception as exception:
            raise Exception("Failed to cleanup", converted_folder) from exception


def converted_folder(
    cache: dict[tuple[str, str, str], TemporaryDirectory],
    wsi_files: dict[str, dict[str, Path]],
    encoder: Encoder,
    file_format: str,
    file: str,
    source: str,
) -> "TemporaryDirectory | None":
    """Convert the slide once with the source (at its `convert_levels`) and cache
    the result, returning its temp dir, or None if the file is missing. Skips if the
    source can not read the file. Conversion is demand driven: it only runs when a
    converted-mode fixture actually requests it."""
    key = (file_format, file, source)
    if key in cache:
        return cache[key]
    file_path = wsi_files[file_format][file]
    if not file_path.exists():
        return None
    identifier = available_source(file_path, source)
    file_parameters = source_parameters(file_format, file, source)
    cache[key] = convert_wsi(file_path, file_parameters, encoder, identifier)
    return cache[key]


@pytest.fixture(scope="module")
def converted_path(
    converted: dict[tuple[str, str, str], TemporaryDirectory],
    wsi_files: dict[str, dict[str, Path]],
    encoder: Encoder,
    file_format: str,
    file: str,
    source: str,
):
    folder = converted_folder(converted, wsi_files, encoder, file_format, file, source)
    if folder is None:
        pytest.skip(f"Skipping {file_format} {file} due to missing file.")
    yield folder


@pytest.fixture(scope="module")
def wsi(
    converted: dict[tuple[str, str, str], TemporaryDirectory],
    wsi_files: dict[str, dict[str, Path]],
    encoder: Encoder,
    file_format: str,
    file: str,
    source: str,
):
    file_path = wsi_files[file_format][file]
    if not file_path.exists():
        pytest.skip(f"Skipping {file_format} {file} due to missing file.")
    if test_parameters[file_format][file]["convert"]:
        folder = converted_folder(
            converted, wsi_files, encoder, file_format, file, source
        )
        assert folder is not None  # the file exists (checked above), so it converts
        wsi = WsiDicom.open(folder.name)
    else:
        wsi = WsiDicomizer.open(
            file_path, preferred_source=available_source(file_path, source)
        )
    yield wsi
    wsi.close()


@pytest.fixture(scope="module")
def opened_wsi(
    wsi_files: dict[str, dict[str, Path]],
    file_format: str,
    file: str,
    source: str,
):
    """The slide opened in-memory with the source (full pyramid, no level
    restriction), for tests that read/compose directly from the source file at any
    level."""
    file_path = wsi_files[file_format][file]
    if not file_path.exists():
        pytest.skip(f"Skipping {file_format} {file} due to missing file.")
    wsi = WsiDicomizer.open(
        file_path, preferred_source=available_source(file_path, source)
    )
    yield wsi
    wsi.close()


@pytest.fixture(scope="module")
def converted_wsi(
    converted: dict[tuple[str, str, str], TemporaryDirectory],
    wsi_files: dict[str, dict[str, Path]],
    encoder: Encoder,
    file_format: str,
    file: str,
    source: str,
):
    """The slide transcoded to DICOM with the source (at its `convert_levels`) and
    reopened, for tests that exercise the converted output."""
    folder = converted_folder(converted, wsi_files, encoder, file_format, file, source)
    if folder is None:
        pytest.skip(f"Skipping {file_format} {file} due to missing file.")
    wsi = WsiDicom.open(folder.name)
    yield wsi
    wsi.close()


@pytest.fixture(scope="module")
def wsi_file(
    wsi_files: dict[str, dict[str, Path]],
    file_format: str,
    file: str,
):
    if file_format not in wsi_files or file not in wsi_files[file_format]:
        pytest.skip(f"Skipping {file_format} {file} due to no test parameters.")
    filepath = wsi_files[file_format][file]
    if not filepath.exists():
        pytest.skip(f"Skipping {file_format} {file} due to missing file.")
    yield filepath


@pytest.fixture(scope="module")
def source_identifier(wsi_file: Path, source: str) -> SourceIdentifier:
    """The identifier of the source a test reads the file with, skipping the test
    if the source can not read it."""
    return available_source(wsi_file, source)


class FakeSource(DicomizerSource):
    """A source that reads nothing but the metadata it is made with.

    Not a mock: the metadata of a source is what is under test here, so the
    behaviour of the class it is a source of is what has to run.
    """

    def __init__(self, base_metadata: WsiDicomizerMetadata, **kwargs):
        self._base_metadata = base_metadata
        super().__init__(filepath=UPath("slide.svs"), encoder=None, **kwargs)

    @staticmethod
    def is_supported(path, file_options: dict[str, Any] | None = None) -> bool:
        return True

    @property
    def base_metadata(self) -> WsiDicomizerMetadata:
        return self._base_metadata

    @property
    def _pixel_format(self):
        raise NotImplementedError()

    @property
    def pyramid_levels(self):
        raise NotImplementedError()

    def _create_level_image_data(self, level_index: int):
        raise NotImplementedError()

    def _create_label_image_data(self):
        raise NotImplementedError()

    def _create_overview_image_data(self):
        raise NotImplementedError()

    def _create_thumbnail_image_data(self):
        raise NotImplementedError()

    def close(self) -> None:
        pass
