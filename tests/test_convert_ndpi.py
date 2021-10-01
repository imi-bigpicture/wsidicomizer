import glob
import json
import os
import unittest
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Tuple

import pytest
from wsidicomizer import WsiDicomizer
from wsidicomizer.interface import create_test_base_dataset
from wsidicom import WsiDicom

ndpi_test_data_dir = os.environ.get(
    "NDPI_TESTDIR",
    "C:/temp/opentile/ndpi/"
)
turbo_path = 'C:/libjpeg-turbo64/bin/turbojpeg.dll'

include_levels = [4, 6]


@pytest.mark.convert_ndpi
class NdpiConvertTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_folders: Dict[
            Path,
            Tuple[WsiDicom, TemporaryDirectory]
        ]
        self.tile_size: Tuple[int, int]

    @classmethod
    def setUpClass(cls):
        cls.tile_size = (1024, 1024)
        cls.test_folders = {}
        folders = cls._get_folders()
        for folder in folders:
            cls.test_folders[folder] = cls.open(folder)

    @classmethod
    def tearDownClass(cls):
        for (wsi, tempdir) in cls.test_folders.values():
            wsi.close()
            tempdir.cleanup()

    @classmethod
    def open(cls, path: Path) -> Tuple[WsiDicom, TemporaryDirectory]:
        filepath = Path(path).joinpath('input.ndpi')
        base_dataset = create_test_base_dataset()
        tempdir = TemporaryDirectory()
        WsiDicomizer.convert(
            filepath,
            Path(tempdir.name),
            base_dataset,
            cls.tile_size,
            include_levels=include_levels
        )
        wsi = WsiDicom.open(str(tempdir.name))
        return (wsi, tempdir)

    @classmethod
    def _get_folders(cls):
        return [
            Path(ndpi_test_data_dir).joinpath(item)
            for item in os.listdir(ndpi_test_data_dir)
        ]

    def test_read_region(self):
        for folder, (wsi, _) in self.test_folders.items():
            json_files = glob.glob(
                str(folder.absolute())+"/read_region/*.json")

            for json_file in json_files:
                with open(json_file, "rt") as f:
                    region = json.load(f)

                im = wsi.read_region(
                    (region["location"]["x"], region["location"]["y"]),
                    region["level"],
                    (region["size"]["width"], region["size"]["height"])
                )
                self.assertEqual(
                    md5(im.tobytes()).hexdigest(),
                    region["md5"]
                )

    def test_read_thumbnail(self):
        for folder, (wsi, _) in self.test_folders.items():
            json_files = glob.glob(
                str(folder.absolute())+"/read_thumbnail/*.json")

            for json_file in json_files:
                with open(json_file, "rt") as f:
                    region = json.load(f)
                im = wsi.read_thumbnail(
                    (region["size"]["width"], region["size"]["height"])
                )
                self.assertEqual(
                    md5(im.tobytes()).hexdigest(),
                    region["md5"]
                )
