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

import os
import unittest
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest
from dicom_validator.spec_reader.edition_reader import EditionReader
from dicom_validator.validator.dicom_file_validator import DicomFileValidator
from parameterized import parameterized
from PIL import Image, ImageChops, ImageStat
from wsidicom import WsiDicom
from wsidicom.errors import WsiDicomNotFoundError

from wsidicomizer.wsidicomizer import WsiDicomizer
from wsidicomizer.openslide import OpenSlide

from .testdata.test_parameters import test_parameters

testdata_dir = Path(os.environ.get('WSIDICOMIZER_TESTDIR', 'tests/testdata'))


@pytest.mark.integrationtest
class WsiDicomizerConvertTests(unittest.TestCase):
    DEFAULT_TILE_SIZE = 512

    @classmethod
    def setUpClass(cls):
        cls.test_folders = {
            (file_format, file): cls.create_test_folder(
                file_format,
                file,
                file_parameters
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        }

    @classmethod
    def tearDownClass(cls):
        for paths in cls.test_folders.values():
            if paths is not None and paths[1] is not None:
                paths[1].cleanup()

    @classmethod
    def create_test_folder(
        cls,
        file_format: str,
        file: str,
        file_parameters: Dict[str, Any]
    ) -> Optional[Tuple[Path, Optional[TemporaryDirectory]]]:
        file_path = testdata_dir.joinpath('slides', file_format, file)
        if not file_path.exists():
            return None
        if not file_parameters['convert']:
            return file_path, None
        include_levels = file_parameters['include_levels']
        tile_size = file_parameters.get('tile_size', cls.DEFAULT_TILE_SIZE)
        converted_path = cls.convert(
            file_path,
            include_levels,
            tile_size
        )
        return file_path, converted_path

    @staticmethod
    def convert(
        path: Path,
        include_levels: Sequence[int],
        tile_size: int
    ) -> TemporaryDirectory:
        tempdir = TemporaryDirectory()
        WsiDicomizer.convert(
            str(path),
            output_path=str(tempdir.name),
            tile_size=tile_size,
            include_levels=include_levels,
            encoding_format='jpeg2000',
            encoding_quality=0
        )
        return tempdir

    @classmethod
    def open_wsi(
        cls,
        file_format: str,
        file: str
    ) -> WsiDicom:
        (original_path, converted_path) = cls.get_paths(file_format, file)
        if converted_path is not None:
            return WsiDicom.open(str(converted_path.name))
        return WsiDicomizer.open(str(original_path))

    @classmethod
    def get_paths(
        cls,
        file_format: str,
        file: str
    ) -> Tuple[Path, Optional[TemporaryDirectory]]:
        paths = cls.test_folders[file_format, file]
        if paths is None:
            raise unittest.SkipTest(
                f'File {file} for format {file_format} not found.'
            )
        return paths

    @classmethod
    def validate(
        cls,
        path: Path
    ) -> List[Tuple[str, str]]:
        standard_path = os.path.join(testdata_dir, 'dicom-validator')
        edition_reader = EditionReader(standard_path)
        revision_path = edition_reader.get_revision('current')
        assert isinstance(revision_path, str)
        json_path = os.path.join(revision_path, 'json')
        validator = DicomFileValidator(
            EditionReader.load_iod_info(json_path),
            EditionReader.load_module_info(json_path),
            EditionReader.load_dict_info(json_path)
        )
        result: Dict[str, Dict[str, str]] = validator.validate_dir(path)
        return [
            (error, tag)
            for tag_error in result.values()
            for tag, error in tag_error.items()
        ]

    @parameterized.expand(
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            if file_parameters['convert']
        ]
    )
    def test_validate(self, file_format: str, file: str):
        (_, converted_path) = self.get_paths(file_format, file)
        assert converted_path is not None
        errors = self.validate(converted_path.name)
        self.assertEqual(errors, [])

    @parameterized.expand(
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ]
    )
    def test_optical_path_not_found(self, file_format: str, file: str):
        with self.open_wsi(file_format, file) as wsi:
            with pytest.raises(WsiDicomNotFoundError):
                wsi.read_tile(0, (0, 0), path='1')

    @parameterized.expand(
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ]
    )
    def test_focal_plane_not_found(self, file_format: str, file: str):
        with self.open_wsi(file_format, file) as wsi:
            with pytest.raises(WsiDicomNotFoundError):
                wsi.read_tile(0, (0, 0), z=1.0)

    @parameterized.expand(
        [
            (
                file_format,
                file,
                region,
                file_parameters['lowest_included_pyramid_level']
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for region in file_parameters['read_region']
        ]
    )
    def test_read_region(
        self,
        file_format: str,
        file: str,
        region: Dict[str, Any],
        lowest_included_level: int
    ):
        with self.open_wsi(file_format, file) as wsi:
            level = region['level'] - lowest_included_level
            im = wsi.read_region(
                (region['location']['x'], region['location']['y']),
                level,
                (region['size']['width'], region['size']['height'])
            )
            self.assertEqual(
                md5(im.tobytes()).hexdigest(),
                region['md5'],
                msg=region
            )

    @parameterized.expand(
        [
            (file_format, file, thumbnail)
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for thumbnail in file_parameters['read_thumbnail']
        ]
    )
    def test_read_thumbnail(
        self,
        file_format: str,
        file: str,
        thumbnail: Dict[str, Any]
    ):
        with self.open_wsi(file_format, file) as wsi:
            im = wsi.read_thumbnail(
                (thumbnail['size']['width'], thumbnail['size']['height'])
            )
            self.assertEqual(
                md5(im.tobytes()).hexdigest(),
                thumbnail['md5'],
                msg=thumbnail
            )

    @parameterized.expand(
        [
            (
                file_format,
                file,
                region,
                file_parameters['lowest_included_pyramid_level']
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for region in file_parameters['read_region_openslide']
        ]
    )
    def test_read_region_openslide(
        self,
        file_format: str,
        file: str,
        region: Dict[str, Any],
        lowest_included_level: int
    ):

        with self.open_wsi(file_format, file) as wsi:
            level = region['level'] - lowest_included_level
            converted = wsi.read_region(
                (region['location']['x'], region['location']['y']),
                level,
                (region['size']['width'], region['size']['height'])
            )

        (original_path, _) = self.get_paths(file_format, file)
        with OpenSlide(original_path) as wsi:
            scale: float = wsi.level_downsamples[region['level']]
            # If scale is not integer image can be blurry
            assert scale.is_integer
            scale = int(scale)
            offset_x = int(wsi.properties.get('openslide.bounds-x', 0))
            offset_y = int(wsi.properties.get('openslide.bounds-y', 0))
            scaled_location_x = (region['location']['x'] * scale) + offset_x
            scaled_location_y = (region['location']['y'] * scale) + offset_y
            reference = wsi.read_region(
                (scaled_location_x, scaled_location_y),
                region['level'],
                (region['size']['width'], region['size']['height'])
            )

        reference_no_alpha = Image.new(
            'RGB',
            reference.size,
            (255, 255, 255)
        )
        reference_no_alpha.paste(reference, mask=reference.split()[3])
        self.assertEqual(converted, reference_no_alpha)

    @parameterized.expand(
        [
            (file_format, file, thumbnail)
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for thumbnail in file_parameters['read_thumbnail']
        ]
    )
    def test_read_thumbnail_openslide(
        self,
        file_format: str,
        file: str,
        thumbnail: Dict[str, Any],
    ):
        with self.open_wsi(file_format, file) as wsi:
            im = wsi.read_thumbnail(
                (thumbnail['size']['width'], thumbnail['size']['height'])
            )

        (original_path, _) = self.get_paths(file_format, file)
        with OpenSlide(original_path) as wsi:
            open_im = wsi.get_thumbnail(
                (thumbnail['size']['width'], thumbnail['size']['height'])
            ).convert('RGB')
        diff = ImageChops.difference(im, open_im)
        for band_rms in ImageStat.Stat(diff).rms:
            self.assertLess(band_rms, 4, (file_format, file, thumbnail))

    @parameterized.expand(
        [
            (file_format, file, file_parameters['photometric_interpretation'])
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ]
    )
    def test_photometric_interpretation(
        self,
        file_format: str,
        file: str,
        photometric_interpretation: str
    ):
        with self.open_wsi(file_format, file) as wsi:
            image_data = wsi.levels[0].default_instance.image_data
            self.assertEqual(
                image_data.photometric_interpretation,
                photometric_interpretation
            )
