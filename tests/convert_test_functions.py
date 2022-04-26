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

import glob
import json
import os
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Optional, Sequence, Tuple

import pytest
from PIL import Image, ImageChops, ImageFilter, ImageStat
from wsidicom import WsiDicom
from wsidicom.errors import WsiDicomNotFoundError
from wsidicomizer.interface import WsiDicomizer

os.add_dll_directory(os.environ['OPENSLIDE'])  # NOQA
from openslide import OpenSlide


class ConvertTestBase:
    include_levels: Sequence[int] = []
    input_filename: str = ""
    test_data_dir: str = ""
    tile_size: Optional[int] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_folders: Dict[
                Path,
                Tuple[WsiDicom, OpenSlide, TemporaryDirectory]
        ] = {}

    @classmethod
    def setUpClass(cls):
        cls.test_folders = {}
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
    def open(cls, path: Path) -> Tuple[
        WsiDicom,
        OpenSlide,
        TemporaryDirectory
    ]:
        filepath = Path(path).joinpath(cls.input_filename)
        tempdir = TemporaryDirectory()
        assert tempdir.name is not None
        WsiDicomizer.convert(
            str(filepath),
            output_path=str(tempdir.name),
            tile_size=cls.tile_size,
            include_levels=cls.include_levels
        )
        wsi = WsiDicom.open(str(tempdir.name))
        open_wsi = OpenSlide(str(filepath))
        return (wsi, open_wsi, tempdir)

    @staticmethod
    def _get_folders(test_data_dir: str):
        return [
            Path(test_data_dir).joinpath(item)
            for item in os.listdir(test_data_dir)
        ]

    def test_optical_path_not_found(self):
        for (wsi, _, _) in self.test_folders.values():
            with pytest.raises(WsiDicomNotFoundError):
                wsi.read_tile(0, (0, 0), path='1')

    def test_focal_plane_not_found(self):
        for (wsi, _, _) in self.test_folders.values():
            with pytest.raises(WsiDicomNotFoundError):
                wsi.read_tile(0, (0, 0), z=1.0)

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
                self.assertEqual(  # type: ignore
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
                self.assertEqual(  # type: ignore
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

                level_size = (
                    wsi.levels[0].size // pow(2, region['level'])
                ).to_tuple()
                # Only run test if level is in open slide wsi
                if level_size in open_wsi.level_dimensions:
                    im = wsi.read_region(
                        (region["location"]["x"], region["location"]["y"]),
                        region["level"],
                        (region["size"]["width"], region["size"]["height"])
                    )
                    index = open_wsi.level_dimensions.index(level_size)
                    scale = int(open_wsi.level_downsamples[index])
                    try:
                        offset_x = open_wsi.properties['openslide.bounds-x']
                        offset_y = open_wsi.properties['openslide.bounds-y']
                    except KeyError:
                        offset_x = offset_y = 0
                    scaled_location_x = (
                        region["location"]["x"] * scale + offset_x
                    )
                    scaled_location_y = (
                        region["location"]["y"] * scale + offset_y
                    )
                    open_im = open_wsi.read_region(
                        (scaled_location_x, scaled_location_y),
                        index,
                        (region["size"]["width"], region["size"]["height"])
                    )
                    no_alpha = Image.new(
                        'RGB',
                        open_im.size,
                        (255, 255, 255)
                    )
                    no_alpha.paste(open_im, mask=open_im.split()[3])
                    open_im = no_alpha

                    blur = ImageFilter.GaussianBlur(2)
                    diff = ImageChops.difference(
                        im.filter(blur),
                        open_im.filter(blur)
                    )
                    print(scaled_location_x, scaled_location_y, index)
                    for band_rms in ImageStat.Stat(diff).rms:
                        self.assertLess(band_rms, 2, region)  # type: ignore

    def test_read_thumbnail_openslide(self):
        for folder, (wsi, open_wsi, _) in self.test_folders.items():
            # Do not run if slide has offset
            if 'openslide.bounds-x' in open_wsi.properties:
                continue
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
                    self.assertLess(band_rms, 2, region)  # type: ignore