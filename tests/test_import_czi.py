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

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Tuple

import pytest
from wsidicom import WsiDicom
from wsidicomizer.czi import CziDicomizer

from .convert_test_functions import ConvertTestBase, OpenSlide


@pytest.mark.import_czi
class CziImportTest(ConvertTestBase, unittest.TestCase):
    testdata_subfolder = 'czi'
    suffix = '.czi'
    tile_size = 512

    def __init__(self, *args, **kwargs):
        super(ConvertTestBase, self).__init__(*args, **kwargs)

    @classmethod
    def open(cls, path: Path) -> Tuple[
        WsiDicom,
        OpenSlide,
        TemporaryDirectory
    ]:
        tempdir = TemporaryDirectory()
        wsi = CziDicomizer.open(
            str(path),
            tile_size=cls.tile_size
        )
        return (wsi, None, tempdir)
