import os
import unittest

import pytest

from .convert_test_functions import ConvertTestBase


@pytest.mark.convert_ndpi
class NdpiConvertTest(ConvertTestBase, unittest.TestCase):
    test_data_dir = os.environ.get(
        "NDPI_TESTDIR",
        "C:/temp/opentile/ndpi/"
    )
    input_filename = 'input.ndpi'
    include_levels = [4, 6]
    turbo_path = os.environ['TURBOJPEG']
    tile_size = 1024

    def __init__(self, *args, **kwargs):
        super(ConvertTestBase, self).__init__(*args, **kwargs)
