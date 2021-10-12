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
    turbo_path = None
    tile_size = None

    def __init__(self, *args, **kwargs):
        super(ConvertTestBase, self).__init__(*args, **kwargs)
