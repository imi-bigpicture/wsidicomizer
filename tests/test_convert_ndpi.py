import glob
import json
import os
import unittest
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Tuple

import pytest
from opentile import OpenTile
from opentile.ndpi_tiler import NdpiTiler
from opentile_dicomizer import WsiDicomizer
from opentile_dicomizer.interface import create_test_base_dataset
from wsidicom import WsiDicom

ndpi_test_data_dir = os.environ.get(
    "NDPI_TESTDIR",
    "C:/temp/opentile/ndpi/"
)
turbo_path = 'C:/libjpeg-turbo64/bin/turbojpeg.dll'


@pytest.mark.convert_ndpi
class NdpiConvertTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_folders: Dict[
            Path,
            Tuple[WsiDicom, NdpiTiler, TemporaryDirectory]
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
        for (wsi, tiler, tempdir) in cls.test_folders.values():
            wsi.close()
            tiler.close()
            tempdir.cleanup()

    @classmethod
    def open(cls, path: Path) -> Tuple[WsiDicom, TemporaryDirectory]:
        filepath = Path(path).joinpath('input.ndpi')
        tiler = OpenTile.open(
            filepath,
            cls.tile_size,
            turbo_path
        )
        base_dataset = create_test_base_dataset()
        tempdir = TemporaryDirectory()
        WsiDicomizer.convert(
            Path(tempdir.name),
            tiler,
            base_dataset,
            include_levels=[4, 6]
        )
        wsi = WsiDicom.open(str(tempdir.name))
        return (wsi, tiler, tempdir)

    @classmethod
    def _get_folders(cls):
        return [
            Path(ndpi_test_data_dir).joinpath(item)
            for item in os.listdir(ndpi_test_data_dir)
        ]

    def test_read_region(self):
        for folder, (wsi, _, _) in self.test_folders.items():
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
        for folder, (wsi, _, _) in self.test_folders.items():
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
