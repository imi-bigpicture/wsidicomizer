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

import io
import os
import unittest

import numpy as np
import pytest
from PIL import Image
from wsidicom.geometry import Size
from wsidicomizer.encoding import JpegEncoder
from wsidicomizer.openslide import OpenSlide, OpenSlideLevelImageData

from .convert_test_functions import ConvertTestBase


@pytest.mark.convert_mirax
class MiraxConvertTest(ConvertTestBase, unittest.TestCase):
    test_data_dir = os.environ.get(
        "MIRAX_TESTDIR",
        "C:/temp/opentile/mirax/"
    )
    input_filename = 'input.mrxs'
    include_levels = [4, 6]
    tile_size: int = 1024

    def __init__(self, *args, **kwargs):
        super(ConvertTestBase, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        openslide_path = list(cls.test_folders.keys())[0]
        cls.openslide = OpenSlide(str(openslide_path)+'/'+cls.input_filename)
        cls.openslide_imagedata = OpenSlideLevelImageData(
            cls.openslide,
            0,
            512,
            JpegEncoder()
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.openslide.close()

    def test_detect_blank_tile(self):
        data = np.full((3, 3, 4), 0)
        self.assertTrue(self.openslide_imagedata._detect_blank_tile(data))

        data = np.full((3, 3, 4), (50, 50, 50, 0))
        self.assertTrue(self.openslide_imagedata._detect_blank_tile(data))

        data = np.full((3, 3, 4), (50, 50, 50, 255))
        self.assertFalse(self.openslide_imagedata._detect_blank_tile(data))

        data = np.full((3, 3, 4), (255, 255, 255, 255))
        self.assertTrue(self.openslide_imagedata._detect_blank_tile(data))

    def test_create_blank_encoded_frame(self):
        size = Size(self.tile_size, self.tile_size)
        frame = self.openslide_imagedata._get_blank_encoded_frame(size)
        image = Image.open(io.BytesIO(frame))
        self.assertEqual(image.size, size.to_tuple())
        data = np.asarray(image)
        self.assertTrue(np.all(data == self.openslide_imagedata.blank_color))

    def test_create_blank_decoded_frame(self):
        size = Size(self.tile_size, self.tile_size)
        image = self.openslide_imagedata._get_blank_decoded_frame(size)
        self.assertEqual(image.size, size.to_tuple())
        data = np.asarray(image)
        self.assertTrue(np.all(data == self.openslide_imagedata.blank_color))
