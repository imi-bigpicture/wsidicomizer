import os
import unittest

import pytest

from .convert_test_functions import ConvertTestBase


@pytest.mark.convert_philips
class PhilipsConvertTest(ConvertTestBase, unittest.TestCase):
    test_data_dir = os.environ.get(
            "PHILIPS_TESTDIR",
            "C:/temp/opentile/philips_tiff/"
        )
    input_filename = 'input.tif'
    include_levels = [4, 6]
    tile_size = None

    def __init__(self, *args, **kwargs):
        super(ConvertTestBase, self).__init__(*args, **kwargs)
