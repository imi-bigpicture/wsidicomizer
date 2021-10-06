import os

import pytest

from .convert_test_functions import ConvertTest


@pytest.mark.convert_ndpi
class NdpiConvertTest(ConvertTest):
    test_data_dir = os.environ.get(
        "NDPI_TESTDIR",
        "C:/temp/opentile/ndpi/"
    )
    input_filename = 'input.ndpi'
    include_levels = [4, 6]
    turbo_path = os.environ['TURBOJPEG']
    tile_size = (1024, 1024)

    def __init__(self, *args, **kwargs):
        super(ConvertTest, self).__init__(*args, **kwargs)
