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
from opentile.philips_tiff_tiler import PhilipsTiffTiler
from wsidicomizer import WsiDicomizer
from wsidicomizer.interface import create_test_base_dataset
from wsidicom import WsiDicom

philips_test_data_dir = os.environ.get(
    "PHILIPS_TESTDIR",
    "C:/temp/opentile/philips_tiff/"
)


turbo_path = 'C:/libjpeg-turbo64/bin/turbojpeg.dll'


@pytest.mark.convert_philips
class NdpiConvertTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_folders: Dict[
            Path,
            Tuple[WsiDicom, PhilipsTiffTiler, TemporaryDirectory]
        ]
        self.tile_size: Tuple[int, int]

    @classmethod
    def setUpClass(cls):
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
        filepath = Path(path).joinpath('input.tif')
        tiler = OpenTile.open(filepath, turbo_path=turbo_path)
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
            Path(philips_test_data_dir).joinpath(item)
            for item in os.listdir(philips_test_data_dir)
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
