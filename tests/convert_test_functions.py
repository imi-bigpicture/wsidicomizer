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

import json
import os
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Sequence, Tuple

import pytest
from PIL import Image, ImageChops, ImageFilter, ImageStat
from wsidicom import WsiDicom
from wsidicom.errors import WsiDicomNotFoundError
from wsidicomizer.interface import WsiDicomizer

os.add_dll_directory(os.environ['OPENSLIDE'])  # NOQA
from openslide import OpenSlide
from unittest import SkipTest

testdata_dir = Path(os.environ.get("OPENTILE_TESTDIR", "tests/testdata"))
REGION_DEFINITIONS_FILE = 'tests/testdata/region_definitions.json'


class ConvertTestBase:
    include_levels: Sequence[int]
    suffix: str
    testdata_subfolder: str
    tile_size: Optional[int] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_folders: Dict[
                Path,
                Tuple[WsiDicom, Optional[OpenSlide], TemporaryDirectory]
        ] = {}

    @classmethod
    def setUpClass(cls):
        cls.test_folders: Dict[
            Path,
            Tuple[WsiDicom, Optional[OpenSlide], TemporaryDirectory]
        ] = {}
        slide_folder = testdata_dir.joinpath(
            'slides',
            cls.testdata_subfolder
        )
        for folder in cls._get_folders(slide_folder):
            filepath = next(
                    (
                        file for file in folder.iterdir()
                        if file.suffix == cls.suffix
                    ),
                    None
                )
            if filepath is not None:
                relative_path = cls._get_relative_path(filepath)
                cls.test_folders[relative_path] = cls.open(filepath)

        if len(cls.test_folders) == 0:
            raise SkipTest(
                f'no test slide files found for {cls.testdata_subfolder}, '
                'skipping'
            )

        with open(REGION_DEFINITIONS_FILE) as json_file:
            cls.test_definitions = json.load(json_file)[cls.testdata_subfolder]

    @classmethod
    def tearDownClass(cls):
        for (wsi, open_wsi, tempdir) in cls.test_folders.values():
            wsi.close()
            tempdir.cleanup()
            if open_wsi is not None:
                open_wsi.close()

    @classmethod
    def open(cls, path: Path) -> Tuple[
        WsiDicom,
        OpenSlide,
        TemporaryDirectory
    ]:
        tempdir = TemporaryDirectory()
        WsiDicomizer.convert(
            str(path),
            output_path=str(tempdir.name),
            tile_size=cls.tile_size,
            include_levels=cls.include_levels
        )
        wsi = WsiDicom.open(str(tempdir.name))
        open_wsi = OpenSlide(str(path))
        return (wsi, open_wsi, tempdir)

    @staticmethod
    def _get_folders(slide_folder: Path) -> List[Path]:
        if not slide_folder.exists():
            return []
        return [
            item for item in slide_folder.iterdir()
            if item.is_dir
        ]

    @staticmethod
    def _get_relative_path(slide_path: Path) -> Path:
        print(slide_path)
        parts = slide_path.parts
        return Path(parts[-2]).joinpath(parts[-1])

    def _skip_if_no_testdefinitions(self):
        if len(self.test_definitions) == 0:
            raise SkipTest(
                f'no test definition found for {self.testdata_subfolder}, '
                'skipping'
            )

    def test_optical_path_not_found(self):
        for (wsi, _, _) in self.test_folders.values():
            with pytest.raises(WsiDicomNotFoundError):
                wsi.read_tile(0, (0, 0), path='1')

    def test_focal_plane_not_found(self):
        for (wsi, _, _) in self.test_folders.values():
            with pytest.raises(WsiDicomNotFoundError):
                wsi.read_tile(0, (0, 0), z=1.0)

    def test_read_region(self):
        self._skip_if_no_testdefinitions()
        for file, test_definitions in self.test_definitions.items():
            if not Path(file) in self.test_folders:
                continue
            (wsi, _, _) = self.test_folders[Path(file)]
            for region in test_definitions['read_region']:
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
        self._skip_if_no_testdefinitions()
        for file, test_definitions in self.test_definitions.items():
            if not Path(file) in self.test_folders:
                continue
            (wsi, _, _) = self.test_folders[Path(file)]
            for region in test_definitions['read_thumbnail']:
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
        self._skip_if_no_testdefinitions()
        for file, test_definitions in self.test_definitions.items():
            if not Path(file) in self.test_folders:
                continue
            (wsi, open_wsi, _) = self.test_folders[Path(file)]
            if open_wsi is None:
                continue
            for region in test_definitions['read_region']:
                level_size = (
                    wsi.levels[0].size // pow(2, region['level'])
                ).to_tuple()
                # Only run test if level is in open slide wsi
                if level_size not in open_wsi.level_dimensions:
                    continue
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
        self._skip_if_no_testdefinitions()
        for file, test_definitions in self.test_definitions.items():
            if not Path(file) in self.test_folders:
                continue
            (wsi, open_wsi, _) = self.test_folders[Path(file)]
            if open_wsi is None:
                continue
            # Do not run if slide has offset
            if 'openslide.bounds-x' in open_wsi.properties:
                continue
            for region in test_definitions['read_thumbnail']:
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
                    print(file)
                    self.assertLess(band_rms, 2, region)  # type: ignore

    def test_photometric_interpretation(self):
        self._skip_if_no_testdefinitions()
        for file, test_definitions in self.test_definitions.items():
            if not Path(file) in self.test_folders:
                continue
            (wsi, _, _) = self.test_folders[Path(file)]
            image_data = wsi.levels[0].default_instance.image_data
            self.assertEqual(
                image_data.photometric_interpretation,
                test_definitions['photometric_interpretation']
            )
