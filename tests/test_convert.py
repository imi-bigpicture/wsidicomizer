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
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List
import numpy as np

import pytest
from dicom_validator.spec_reader.edition_reader import EditionReader
from dicom_validator.validator.dicom_file_validator import DicomFileValidator
from PIL import Image, ImageChops, ImageStat
from wsidicom import WsiDicom
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import SizeMm
from wsidicom.metadata import Image as ImageMetadata

from wsidicomizer.extras.openslide.openslide import (
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    OpenSlide,
)
from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.wsidicomizer import WsiDicomizer

from .conftest import Jpeg2kTestEncoder, test_parameters


@pytest.mark.integrationtest
class TestWsiDicomizerConvert:
    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            if file_parameters["convert"]
        ],
    )
    def test_validate(
        self,
        file_format: str,
        file: str,
        testdata_dir: Path,
        converted: Dict[str, Dict[str, TemporaryDirectory]],
    ):
        # Arrange
        converted_path = converted[file_format][file]
        standard_path = os.path.join(testdata_dir, "dicom-validator")
        edition_reader = EditionReader(standard_path)
        revision_path = edition_reader.get_revision("current")
        assert isinstance(revision_path, Path)
        json_path = revision_path.joinpath("json")
        validator = DicomFileValidator(EditionReader.load_dicom_info(json_path))

        # Act
        result: Dict[str, Dict[str, Dict[str, List[str]]]] = validator.validate_dir(
            converted_path.name
        )

        # Assert
        errors_per_module = {
            module: {tag: error for error, tags in errors.items() for tag in tags}
            for module_errors in result.values()
            for module, errors in module_errors.items()
        }
        module_errors_to_ignore = {
            # These are not required for TILED_FULL organization type
            "Plane Position (Slide)": [
                "(0040,072A)",
                "(0040,073A)",
                "(0048,021E)",
                "(0048,021F)",
            ]
        }
        for module, module_errors in module_errors_to_ignore.items():
            errors = errors_per_module.get(module, None)
            if errors is not None:
                for module_error in module_errors:
                    errors.pop(module_error, None)
                if len(errors) == 0:
                    errors_per_module.pop(module)

        assert len(errors_per_module) == 0

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ],
    )
    def test_optical_path_not_found(
        self, file_format: str, file: str, wsis: Dict[str, Dict[str, WsiDicom]]
    ):
        # Arrange
        wsi = wsis[file_format][file]

        # Act & Assert
        with pytest.raises(WsiDicomNotFoundError):
            wsi.read_tile(0, (0, 0), path="1")

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ],
    )
    def test_focal_plane_not_found(
        self, file_format: str, file: str, wsis: Dict[str, Dict[str, WsiDicom]]
    ):
        # Arrange
        wsi = wsis[file_format][file]

        # Act & Assert
        with pytest.raises(WsiDicomNotFoundError):
            wsi.read_tile(0, (0, 0), z=1.0)

    @pytest.mark.parametrize(
        ["file_format", "file", "region", "lowest_included_level"],
        [
            (
                file_format,
                file,
                region,
                file_parameters["lowest_included_pyramid_level"],
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for region in file_parameters["read_region"]
        ],
    )
    def test_read_region_from_converted_file_should_match_hash(
        self,
        file_format: str,
        file: str,
        region: Dict[str, Any],
        lowest_included_level: int,
        wsis: Dict[str, Dict[str, WsiDicom]],
    ):
        # Arrange
        wsi = wsis[file_format][file]
        level = region["level"] - lowest_included_level

        # Act
        im = wsi.read_region(
            (region["location"]["x"], region["location"]["y"]),
            level,
            (region["size"]["width"], region["size"]["height"]),
        )

        # Assert
        assert (
            md5(im.tobytes()).hexdigest() == region["md5"]
        ), f"{file_format}: {file} lowest level {lowest_included_level} {region}"

    @pytest.mark.parametrize(
        ["file_format", "file", "thumbnail"],
        [
            (file_format, file, thumbnail)
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for thumbnail in file_parameters["read_thumbnail"]
        ],
    )
    def test_read_thumbnail_from_converted_file_should_match_hash(
        self,
        file_format: str,
        file: str,
        thumbnail: Dict[str, Any],
        wsis: Dict[str, Dict[str, WsiDicom]],
    ):
        # Arrange
        wsi = wsis[file_format][file]

        # Act
        im = wsi.read_thumbnail(
            (thumbnail["size"]["width"], thumbnail["size"]["height"])
        )

        # Assert
        assert (
            md5(im.tobytes()).hexdigest() == thumbnail["md5"]
        ), f"{file_format}: {file} {thumbnail}"

    @pytest.mark.parametrize(
        ["file_format", "file", "region", "lowest_included_level"],
        [
            (
                file_format,
                file,
                region,
                file_parameters["lowest_included_pyramid_level"],
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for region in file_parameters["read_region_openslide"]
        ],
    )
    def test_read_region_from_converted_file_should_match_openslide(
        self,
        file_format: str,
        file: str,
        region: Dict[str, Any],
        lowest_included_level: int,
        wsi_files: Dict[str, Dict[str, Path]],
        wsis: Dict[str, Dict[str, WsiDicom]],
    ):
        # Arrange
        wsi = wsis[file_format][file]
        level = region["level"] - lowest_included_level
        original_path = wsi_files[file_format][file]
        with OpenSlide(original_path) as openslide_wsi:
            scale: float = openslide_wsi.level_downsamples[region["level"]]
            # If scale is not integer image can be blurry
            assert scale.is_integer
            scale = int(scale)
            offset_x = int(openslide_wsi.properties.get(PROPERTY_NAME_BOUNDS_X, 0))
            offset_y = int(openslide_wsi.properties.get(PROPERTY_NAME_BOUNDS_Y, 0))
            scaled_location = (
                (region["location"]["x"] * scale) + offset_x,
                (region["location"]["y"] * scale) + offset_y,
            )
            reference = openslide_wsi.read_region(
                scaled_location,
                region["level"],
                (region["size"]["width"], region["size"]["height"]),
            )

            reference_no_alpha = Image.new("RGB", reference.size, (255, 255, 255))
            reference_no_alpha.paste(reference, mask=reference.split()[3])

        # Act
        converted = wsi.read_region(
            (region["location"]["x"], region["location"]["y"]),
            level,
            (region["size"]["width"], region["size"]["height"]),
        )

        # Assert
        assert (
            md5(converted.tobytes()).hexdigest()
            == md5(reference_no_alpha.tobytes()).hexdigest()
        ), (
            f"{file_format}: {file} {region} does not match openslide at ",
            scaled_location,
            region["level"],
            region["size"]["height"],
        )

    @pytest.mark.parametrize(
        ["file_format", "file", "thumbnail"],
        [
            (file_format, file, thumbnail)
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for thumbnail in file_parameters["read_thumbnail"]
        ],
    )
    def test_read_thumbnail_from_converted_file_should_almost_match_thumbnail(
        self,
        file_format: str,
        file: str,
        thumbnail: Dict[str, Any],
        wsi_files: Dict[str, Dict[str, Path]],
        wsis: Dict[str, Dict[str, WsiDicom]],
    ):
        # Arrange
        wsi = wsis[file_format][file]
        original_path = wsi_files[file_format][file]
        with OpenSlide(original_path) as openslide_wsi:
            open_im = openslide_wsi.get_thumbnail(
                (thumbnail["size"]["width"], thumbnail["size"]["height"])
            ).convert("RGB")

        # Act
        im = wsi.read_thumbnail(
            (thumbnail["size"]["width"], thumbnail["size"]["height"])
        )

        # Assert
        diff = ImageChops.difference(im, open_im)
        for band_rms in ImageStat.Stat(diff).rms:
            assert band_rms < 4, f"{file_format}: {file} {thumbnail}"

    @pytest.mark.parametrize(
        ["file_format", "file", "photometric_interpretation"],
        [
            (file_format, file, file_parameters["photometric_interpretation"])
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
    )
    def test_photometric_interpretation(
        self,
        file_format: str,
        file: str,
        photometric_interpretation: str,
        wsis: Dict[str, Dict[str, WsiDicom]],
    ):
        # Arrange
        wsi = wsis[file_format][file]

        # Act
        image_data = wsi.levels[0].default_instance.image_data

        # Assert
        assert image_data.photometric_interpretation == photometric_interpretation

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ],
    )
    def test_replace_label_should_equal_new_label(
        self, file_format: str, file: str, wsi_files: Dict[str, Dict[str, Path]]
    ):
        # Arrange
        wsi_file = wsi_files[file_format][file]

        label = Image.new("RGB", (256, 256), (128, 128, 128))

        # Act
        with TemporaryDirectory() as temp_dir:
            WsiDicomizer.convert(
                wsi_file,
                temp_dir,
                include_levels=[-1],
                label=label,
                encoding=Jpeg2kTestEncoder(),
            )

            # Assert
            with WsiDicom.open(temp_dir) as wsi:
                new_label = wsi.read_label()

        assert np.array_equal(np.array(new_label), np.array(label))

    @pytest.mark.parametrize(
        ["file_format", "file", "expected_image_coordinate_system"],
        [
            (file_format, file, file_parameters["image_coordinate_system"])
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
    )
    def test_image_coordinate_system(
        self,
        file_format: str,
        file: str,
        expected_image_coordinate_system: Dict[str, float],
        wsis: Dict[str, Dict[str, WsiDicom]],
    ):
        # Arrange
        wsi = wsis[file_format][file]

        # Act
        image_coordinate_system = wsi.levels[
            0
        ].default_instance.image_data.image_coordinate_system

        # Arrange
        assert image_coordinate_system is not None
        assert image_coordinate_system.origin.x == expected_image_coordinate_system["x"]
        assert image_coordinate_system.origin.y == expected_image_coordinate_system["y"]

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ],
    )
    def test_change_pixel_spacing(
        self, file_format: str, file: str, wsi_files: Dict[str, Dict[str, Path]]
    ):
        # Arrange
        wsi_file = wsi_files[file_format][file]
        given_pixel_spacing = SizeMm(47, 47)
        metadata = WsiDicomizerMetadata(
            image=ImageMetadata(pixel_spacing=given_pixel_spacing)
        )

        # Act
        with WsiDicomizer.open(wsi_file, metadata=metadata) as wsi:
            base_pixel_spacing = wsi.pixel_spacing

        # Assert
        assert base_pixel_spacing == given_pixel_spacing
