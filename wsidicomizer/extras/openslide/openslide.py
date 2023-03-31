#    Copyright 2021, 2022, 2023 SECTRA AB
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

"""Importing openslide module after loading library if needed."""

import os
from ctypes.util import find_library
from pathlib import Path

# On windows, use find_library to find directory with openslide dll in
# the Path environmental variable.
if os.name == "nt":
    openslide_lib_path = find_library("libopenslide-0")
    if openslide_lib_path is not None:
        openslide_dir = str(Path(openslide_lib_path).parent)
    else:
        openslide_lib_dir = os.environ.get("OPENSLIDE")
        if openslide_lib_dir is not None:
            openslide_lib_path = Path(openslide_lib_dir).joinpath("libopenslide-0.dll")
            if not openslide_lib_path.exists():
                openslide_lib_path = None
    if openslide_lib_path is None:
        raise ModuleNotFoundError(
            "Could not find libopenslide-0.dll in the directories specified "
            "in the `Path` or `OPENSLIDE` environmental variable. Please add "
            "the directory with openslide bin content to the `Path` or  "
            "OPENSLIDE environmental variable."
        )
    openslide_dir = str(Path(openslide_lib_path).parent)
    os.add_dll_directory(openslide_dir)

from openslide import (
    PROPERTY_NAME_BACKGROUND_COLOR,
    PROPERTY_NAME_BOUNDS_HEIGHT,
    PROPERTY_NAME_BOUNDS_WIDTH,
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    PROPERTY_NAME_MPP_X,
    PROPERTY_NAME_MPP_Y,
    PROPERTY_NAME_OBJECTIVE_POWER,
    PROPERTY_NAME_VENDOR,
    OpenSlide,
)
from openslide._convert import argb2rgba as convert_argb_to_rgba
from openslide.lowlevel import _read_region, get_associated_image_names
