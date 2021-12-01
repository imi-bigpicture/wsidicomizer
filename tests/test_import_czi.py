import glob
import json
import os
import unittest
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Tuple

import pytest
from wsidicom import WsiDicom
from wsidicomizer.czi import CziDicomizer
from wsidicomizer.dataset import create_default_modules


@pytest.mark.import_czi
class CziImportTest(unittest.TestCase):
    input_filename: str = 'input.czi'
    test_data_dir: str = os.environ.get(
        "CZI_TESTDIR",
        "C:/temp/opentile/czi/"
    )
    tile_size = 512
    test_folders: Dict[
            Path,
            Tuple[WsiDicom, TemporaryDirectory]
    ] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        cls.test_folders = {}
        assert cls.test_data_dir is not None
        folders = cls._get_folders(cls.test_data_dir)
        for folder in folders:
            cls.test_folders[folder] = cls.open(folder)

    @classmethod
    def tearDownClass(cls):
        for (wsi, tempdir) in cls.test_folders.values():
            wsi.close()
            tempdir.cleanup()

    @classmethod
    def open(cls, path: Path) -> Tuple[WsiDicom, TemporaryDirectory]:
        filepath = Path(path).joinpath(cls.input_filename)
        base_dataset = create_default_modules()
        tempdir = TemporaryDirectory()
        wsi = CziDicomizer.open(
            str(filepath),
            base_dataset,
            cls.tile_size
        )
        return (wsi, tempdir)

    @staticmethod
    def _get_folders(test_data_dir: str):
        return [
            Path(test_data_dir).joinpath(item)
            for item in os.listdir(test_data_dir)
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
                print(region)
                self.assertEqual(
                    md5(im.tobytes()).hexdigest(),
                    region["md5"],
                    msg=region
                )
