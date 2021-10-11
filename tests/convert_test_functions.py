import glob
import json
import os
import unittest
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Tuple, List

from wsidicomizer import WsiDicomizer
from wsidicomizer.dataset import create_default_dataset
from wsidicom import WsiDicom
from PIL import ImageChops, ImageStat, ImageFilter

os.add_dll_directory(os.environ['OPENSLIDE'])  # NOQA
from openslide import OpenSlide


class ConvertTest(unittest.TestCase):
    include_levels: List[int] = None
    input_filename: str = None
    test_data_dir: str = None
    turbo_path: str = None
    tile_size: Tuple[int, int] = None
    test_folders: Dict[
            Path,
            Tuple[WsiDicom, OpenSlide, TemporaryDirectory]
    ] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        cls.test_folders = {}
        if cls.test_data_dir is not None:
            folders = cls._get_folders(cls.test_data_dir)
            for folder in folders:
                cls.test_folders[folder] = cls.open(folder)

    @classmethod
    def tearDownClass(cls):
        for (wsi, open_wsi, tempdir) in cls.test_folders.values():
            wsi.close()
            tempdir.cleanup()
            open_wsi.close()

    @classmethod
    def open(cls, path: Path) -> Tuple[Path, WsiDicom, TemporaryDirectory]:
        filepath = Path(path).joinpath(cls.input_filename)
        base_dataset = create_default_dataset()
        tempdir = TemporaryDirectory()
        WsiDicomizer.convert(
            str(filepath),
            Path(tempdir.name),
            base_dataset,
            tile_size=cls.tile_size,
            include_levels=cls.include_levels
        )
        wsi = WsiDicom.open(str(tempdir.name))
        open_wsi = OpenSlide(str(filepath))
        return (wsi, open_wsi, tempdir)

    @staticmethod
    def _get_folders(test_data_dir: Path):
        return [
            Path(test_data_dir).joinpath(item)
            for item in os.listdir(test_data_dir)
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
                print(region)
                self.assertEqual(
                    md5(im.tobytes()).hexdigest(),
                    region["md5"],
                    msg=region
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
                print(region)
                self.assertEqual(
                    md5(im.tobytes()).hexdigest(),
                    region["md5"],
                    msg=region
                )

    def test_read_region_openslide(self):
        for folder, (wsi, open_wsi, _) in self.test_folders.items():
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
                level_size = (
                    wsi.levels[0].size // pow(2, region['level'])
                ).to_tuple()
                # Only run test if level is in open slide wsi
                if level_size in open_wsi.level_dimensions:
                    index = open_wsi.level_dimensions.index(level_size)
                    scale = int(open_wsi.level_downsamples[index])
                    scaled_location_x = region["location"]["x"] * scale
                    scaled_location_y = region["location"]["y"] * scale
                    open_im = open_wsi.read_region(
                        (scaled_location_x, scaled_location_y),
                        index,
                        (region["size"]["width"], region["size"]["height"])
                    ).convert('RGB')
                    blur = ImageFilter.GaussianBlur(2)
                    diff = ImageChops.difference(
                        im.filter(blur),
                        open_im.filter(blur)
                    )
                    for band_rms in ImageStat.Stat(diff).rms:
                        self.assertLess(band_rms, 2, region)

    def test_read_thumbnail_openslide(self):
        for folder, (wsi, open_wsi, _) in self.test_folders.items():
            json_files = glob.glob(
                str(folder.absolute())+"/read_thumbnail/*.json")

            for json_file in json_files:
                with open(json_file, "rt") as f:
                    region = json.load(f)
                im = wsi.read_thumbnail(
                    (region["size"]["width"], region["size"]["height"])
                )
                open_im = open_wsi.get_thumbnail(
                    (region["size"]["width"], region["size"]["height"])
                ).convert('RGB')
                blur = ImageFilter.GaussianBlur(2)
                diff = ImageChops.difference(
                    im.filter(blur),
                    open_im.filter(blur)
                )
                for band_rms in ImageStat.Stat(diff).rms:
                    self.assertLess(band_rms, 2, region)
