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

import pytest

from .convert_test_functions import ConvertTestBase


@pytest.mark.convert_svs
class SvsConvertTest(ConvertTestBase, unittest.TestCase):
    test_data_dir = os.environ.get(
        "SVS_TESTDIR",
        "C:/temp/opentile/svs/"
    )
    input_filename = 'input.svs'
    include_levels = [4, 6]
    tile_size = None

    def __init__(self, *args, **kwargs):
        super(ConvertTestBase, self).__init__(*args, **kwargs)
