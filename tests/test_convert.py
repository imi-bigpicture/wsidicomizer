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

import math
import os
import platform
from hashlib import md5
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pytest
from dicom_validator.spec_reader.edition_reader import EditionReader
from dicom_validator.validator.dicom_file_validator import DicomFileValidator
from PIL import Image, ImageChops, ImageStat
from pydicom import Dataset
from wsidicom import WsiDicom
from wsidicom.codec import Encoder
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import PointMm, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import WsiMetadata

from wsidicomizer.extras.openslide.openslide import (
    PROPERTY_NAME_BOUNDS_X,
    PROPERTY_NAME_BOUNDS_Y,
    OpenSlide,
)
from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.wsidicomizer import WsiDicomizer

from .conftest import Jpeg2kTestEncoder, test_parameters


@pytest.fixture(scope="module")
def validator(
    testdata_dir: Path,
):
    standard_path = os.path.join(testdata_dir, "dicom-validator")
    edition_reader = EditionReader(standard_path)
    edition_reader.get_editions()
    revision_path = edition_reader.get_revision("current")
    assert isinstance(revision_path, Path)
    json_path = revision_path.joinpath("json")
    yield DicomFileValidator(EditionReader.load_dicom_info(json_path))


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
        scope="module",
    )
    def test_validate(
        self,
        validator: DicomFileValidator,
        converted_path: TemporaryDirectory,
    ):
        # Arrange

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
            ],
            # Validator flags Series Number as unexpected due to error in DICOM 2024a
            "Root": ["(0020,0011)"],
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
        scope="module",
    )
    def test_optical_path_not_found(self, wsi: WsiDicom):
        # Arrange

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
        scope="module",
    )
    def test_focal_plane_not_found(self, wsi: WsiDicom):
        # Arrange

        # Act & Assert
        with pytest.raises(WsiDicomNotFoundError):
            wsi.read_tile(0, (0, 0), z=9999.0)

    @pytest.mark.parametrize(
        [
            "file_format",
            "file",
            "region",
            "lowest_included_level",
            "skip_hash_test_platforms",
        ],
        [
            (
                file_format,
                file,
                region,
                file_parameters["lowest_included_pyramid_level"],
                file_parameters.get("skip_hash_test_platforms", []),
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for region in file_parameters["read_region"]
        ],
        scope="module",
    )
    def test_read_region_from_converted_file_should_match_hash(
        self,
        file_format: str,
        file: str,
        region: Dict[str, Any],
        lowest_included_level: int,
        skip_hash_test_platforms: List[str],
        wsi: WsiDicom,
    ):
        # Arrange
        if platform.system() in skip_hash_test_platforms:
            pytest.skip(f"Skipping hash test for {platform.system()}.")
        level = region["level"] - lowest_included_level

        # Act
        im = wsi.read_region(
            (region["location"]["x"], region["location"]["y"]),
            level,
            (region["size"]["width"], region["size"]["height"]),
            z=region.get("z", None),
        )

        # Assert
        assert (
            md5(im.tobytes()).hexdigest() == region["md5"]
        ), f"{file_format}: {file} lowest level {lowest_included_level} {region}"

    @pytest.mark.parametrize(
        ["file_format", "file", "thumbnail", "skip_hash_test_platforms"],
        [
            (
                file_format,
                file,
                thumbnail,
                file_parameters.get("skip_hash_test_platforms", []),
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for thumbnail in file_parameters["read_thumbnail"]
        ],
        scope="module",
    )
    def test_read_thumbnail_from_converted_file_should_match_hash(
        self,
        file_format: str,
        file: str,
        thumbnail: Dict[str, Any],
        wsi: WsiDicom,
        skip_hash_test_platforms: List[str],
    ):
        # Arrange
        if platform.system() in skip_hash_test_platforms:
            pytest.skip(f"Skipping hash test for {platform.system()}.")

        # Act
        im = wsi.read_thumbnail(
            (thumbnail["size"]["width"], thumbnail["size"]["height"]),
            force_generate=True,
        )

        # Assert
        assert (
            md5(im.tobytes()).hexdigest() == thumbnail["md5"]
        ), f"{file_format}: {file} {thumbnail}"

    @pytest.mark.parametrize(
        [
            "file_format",
            "file",
            "region",
            "lowest_included_level",
            "skip_hash_test_platforms",
        ],
        [
            (
                file_format,
                file,
                region,
                file_parameters["lowest_included_pyramid_level"],
                file_parameters.get("skip_hash_test_platforms", []),
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            for region in file_parameters["read_region_openslide"]
            if file_parameters["openslide"]
        ],
        scope="module",
    )
    def test_read_region_from_converted_file_should_match_openslide(
        self,
        file_format: str,
        file: str,
        region: Dict[str, Any],
        lowest_included_level: int,
        skip_hash_test_platforms: List[str],
        wsi_file: Path,
        wsi: WsiDicom,
    ):
        # Arrange
        if platform.system() in skip_hash_test_platforms:
            pytest.skip(f"Skipping hash test for {platform.system()}.")
        level = region["level"] - lowest_included_level
        with OpenSlide(wsi_file) as openslide_wsi:
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
            z=0,
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
            if file_parameters["openslide"]
        ],
        scope="module",
    )
    def test_read_thumbnail_from_converted_file_should_almost_match_openslide_thumbnail(
        self,
        file_format: str,
        file: str,
        thumbnail: Dict[str, Any],
        wsi_file: Path,
        wsi: WsiDicom,
    ):
        # Arrange
        with OpenSlide(wsi_file) as openslide_wsi:
            open_im = openslide_wsi.get_thumbnail(
                (thumbnail["size"]["width"], thumbnail["size"]["height"])
            ).convert("RGB")

        # Act
        im = wsi.read_thumbnail(
            (thumbnail["size"]["width"], thumbnail["size"]["height"]),
            force_generate=True,
        )

        # Assert
        diff = ImageChops.difference(im, open_im)
        for band_rms in ImageStat.Stat(diff).rms:
            assert band_rms < 4, f"{file_format}: {file} {thumbnail}"

    @pytest.mark.parametrize(
        ["file_format", "file", "native_photometric_interpretation", "is_converted"],
        [
            (
                file_format,
                file,
                file_parameters["photometric_interpretation"],
                file_parameters["convert"],
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
        scope="module",
    )
    def test_photometric_interpretation(
        self,
        encoder: Encoder,
        native_photometric_interpretation: str,
        is_converted: bool,
        wsi: WsiDicom,
    ):
        # Arrange
        expected_photometric_interpretation = (
            encoder.photometric_interpretation
            if is_converted
            else native_photometric_interpretation
        )

        # Act
        image_data = wsi.pyramids[0].base_level.default_instance.image_data

        # Assert
        assert (
            image_data.photometric_interpretation == expected_photometric_interpretation
        )

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
            if format_files[file]["convert"]
        ],
        scope="module",
    )
    def test_replace_label_should_equal_new_label(self, wsi_file: Path):
        # Arrange

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
            (
                file_format,
                file,
                PointMm(
                    file_parameters["image_coordinate_system"]["x"],
                    file_parameters["image_coordinate_system"]["y"],
                ),
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
        scope="module",
    )
    def test_image_coordinate_system(
        self,
        expected_image_coordinate_system: PointMm,
        wsi: WsiDicom,
    ):
        # Arrange

        # Act
        image_coordinate_systems = [
            level.image_coordinate_system for level in wsi.pyramid
        ]
        if wsi.pyramid.thumbnails is not None and len(wsi.pyramid.thumbnails) > 0:
            image_coordinate_systems.append(
                wsi.pyramid.thumbnails[0].image_coordinate_system
            )

        # Arrange
        for image_coordinate_system in image_coordinate_systems:
            assert image_coordinate_system is not None
            assert image_coordinate_system.origin == expected_image_coordinate_system

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ],
        scope="module",
    )
    def test_change_pixel_spacing(self, wsi_file: Path):
        # Arrange
        given_pixel_spacing = SizeMm(47, 47)
        metadata = WsiDicomizerMetadata(
            image=ImageMetadata(pixel_spacing=given_pixel_spacing)
        )

        # Act
        with WsiDicomizer.open(wsi_file, metadata=metadata) as wsi:
            base_pixel_spacing = wsi.pixel_spacing

        # Assert
        assert base_pixel_spacing == given_pixel_spacing

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
        scope="module",
    )
    def test_icc_profile(
        self,
        wsi: WsiDicom,
    ):
        # Arrange

        # Act
        icc_profile = wsi.pyramids[0].metadata.optical_paths[0].icc_profile

        # Arrange
        assert icc_profile is not None

    @pytest.mark.parametrize(
        ["file_format", "file", "embedded_thumbnail"],
        [
            (file_format, file, file_parameters["embedded_thumbnail_size"] is not None)
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
        scope="module",
    )
    def test_embedded_thumbnail(self, wsi: WsiDicom, embedded_thumbnail: bool):
        # Arrange

        # Act
        has_thumbnail_instances = (
            wsi.pyramid.thumbnails is not None and len(wsi.pyramid.thumbnails) > 0
        )

        # Assert
        assert has_thumbnail_instances == embedded_thumbnail

    @pytest.mark.parametrize(
        ["file_format", "file", "embedded_thumbnail_size"],
        [
            (file_format, file, file_parameters["embedded_thumbnail_size"])
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            if file_parameters["embedded_thumbnail_size"] is not None
        ],
        scope="module",
    )
    def test_embedded_thumbnail_size(
        self, wsi: WsiDicom, embedded_thumbnail_size: Tuple[int, int]
    ):
        # Arrange
        assert wsi.pyramid.thumbnails is not None
        # Act
        thumnail = wsi.pyramid.thumbnails[0]

        # Assert
        assert thumnail.size == Size.from_tuple(embedded_thumbnail_size)

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ],
        scope="module",
    )
    def test_metadata_post_processor_with_dataset(self, wsi_file: Path):
        # Arrange
        given_patient_age = "042Y"
        dataset = Dataset()
        dataset.PatientAge = given_patient_age

        # Act
        with WsiDicomizer.open(wsi_file, metadata_post_processor=dataset) as wsi:
            patient_age = wsi.pyramid.datasets[0].PatientAge

        # Assert
        assert patient_age == given_patient_age

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (file_format, file)
            for file_format, format_files in test_parameters.items()
            for file in format_files.keys()
        ],
        scope="module",
    )
    def test_metadata_post_processor_with_callback(self, wsi_file: Path):
        # Arrange
        given_patient_age = "042Y"

        def callback(dataset: Dataset, metadata: WsiMetadata) -> Dataset:
            dataset.PatientAge = given_patient_age
            return dataset

        # Act
        with WsiDicomizer.open(wsi_file, metadata_post_processor=callback) as wsi:
            patient_age = wsi.pyramid.datasets[0].PatientAge

        # Assert
        assert patient_age == given_patient_age

    @pytest.mark.parametrize(
        ["file_format", "file", "expected_pixel_spacings"],
        [
            (
                file_format,
                file,
                [
                    SizeMm.from_tuple(spacing)
                    for spacing in file_parameters["pixel_spacings"]
                ],
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
        scope="module",
    )
    def test_pixel_spacings(
        self, wsi: WsiDicom, expected_pixel_spacings: Iterable[SizeMm]
    ):
        # Arrange

        # Act
        pixel_spacings = [level.pixel_spacing for level in wsi.pyramids[0].levels]

        # Assert
        assert expected_pixel_spacings == pixel_spacings

    @pytest.mark.parametrize(
        ["file_format", "file", "expected_thumbnail_pixel_spacing"],
        [
            (
                file_format,
                file,
                SizeMm.from_tuple(file_parameters["thumbnail_pixel_spacing"]),
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
            if file_parameters["thumbnail_pixel_spacing"] is not None
        ],
        scope="module",
    )
    def test_thumbnail_pixel_spacing(
        self, wsi: WsiDicom, expected_thumbnail_pixel_spacing: SizeMm
    ):
        # Arrange
        assert (
            wsi.pyramids[0].thumbnails is not None
            and len(wsi.pyramids[0].thumbnails) > 0
        )

        # Act
        pixel_spacing = wsi.pyramids[0].thumbnails[0].pixel_spacing

        # Assert
        assert expected_thumbnail_pixel_spacing == pixel_spacing

    @pytest.mark.parametrize(
        ["file_format", "file", "expected_imaged_size"],
        [
            (
                file_format,
                file,
                SizeMm.from_tuple(file_parameters["imaged_size"]),
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
        scope="module",
    )
    def test_imaged_size(self, wsi: WsiDicom, expected_imaged_size: SizeMm):
        # Arrange

        # Act
        imaged_sizes = [
            level.default_instance.image_data.imaged_size
            for level in wsi.pyramid.levels
        ]
        if wsi.pyramid.thumbnails is not None and len(wsi.pyramid.thumbnails) > 0:
            imaged_sizes.append(
                wsi.pyramid.thumbnails[0].default_instance.image_data.imaged_size
            )

        # Assert
        for imaged_size in imaged_sizes:
            assert imaged_size == expected_imaged_size

    @pytest.mark.parametrize(
        ["file_format", "file", "expected_focal_planes"],
        [
            (
                file_format,
                file,
                file_parameters["focal_planes"],
            )
            for file_format, format_files in test_parameters.items()
            for file, file_parameters in format_files.items()
        ],
        scope="module",
    )
    def test_focal_planes(self, wsi: WsiDicom, expected_focal_planes: List[float]):
        # Arrange

        # Act
        focal_planes = wsi.pyramid.base_level.focal_planes

        # Assert
        assert set(focal_planes) == set(expected_focal_planes)

    @pytest.mark.parametrize(
        ["file_format", "file"],
        [
            (
                file_format,
                file,
            )
            for file_format, format_files in test_parameters.items()
            for file, _ in format_files.items()
        ],
        scope="module",
    )
    def test_imaged_size_compared_to_pixel_spacing(self, wsi: WsiDicom):
        # Arrange
        expected_pixel_spacings = [
            SizeMm(
                level.default_instance.mm_size.width
                / level.default_instance.size.width,
                level.default_instance.mm_size.height
                / level.default_instance.size.height,
            )
            for level in wsi.levels
            if level.default_instance.mm_size is not None
        ]

        # Act
        pixel_sizes = [
            level.default_instance.image_data.pixel_spacing
            for level in wsi.pyramid.levels
            if level.default_instance.image_data.pixel_spacing is not None
        ]

        # Assert
        for expected_pixel_spacing, pixel_size in zip(
            expected_pixel_spacings, pixel_sizes
        ):
            assert math.isclose(
                expected_pixel_spacing.width, pixel_size.width, rel_tol=1.5e-3
            ), f"Width mismatch: {expected_pixel_spacing.width} != {pixel_size.width}"
            assert math.isclose(
                expected_pixel_spacing.height, pixel_size.height, rel_tol=1.5e-3
            ), f"Height mismatch: {expected_pixel_spacing.height} != {pixel_size.height}"
