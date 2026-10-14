#    Copyright 2026 SECTRA AB
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
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydicom.uid import JPEG2000, JPEGBaseline8Bit
from upath import UPath
from wsidicom.geometry import Point, Size

from wsidicomizer.sources.vsi import VsiSource
from wsidicomizer.sources.vsi.ets import EtsFile
from wsidicomizer.sources.vsi.vsi_metadata import LABEL_NAME, OVERVIEW_NAME, VsiImage

J2K_SOC_SIZ = bytes.fromhex("ff4fff51")
JPEG_SOI = bytes.fromhex("ffd8")


def _get_slide(testdata_dir: Path, name: str) -> Path:
    slide = next(testdata_dir.joinpath("slides", "vsi", name).glob("*.vsi"), None)
    if slide is None:
        pytest.skip(f"vsi test data {name} not available")
    return slide


@pytest.fixture
def slide(testdata_dir: Path) -> Path:
    """A slide scan with JPEG 2000 tiles."""
    return _get_slide(testdata_dir, "OS-1")


@pytest.fixture
def jpeg_slide(testdata_dir: Path) -> Path:
    """A slide scan with JPEG tiles."""
    return _get_slide(testdata_dir, "Image_V4.1_BF")


@pytest.fixture
def multi_channel_slide(testdata_dir: Path) -> Path:
    """A fluorescence scan with several channels."""
    return _get_slide(testdata_dir, "Image_V4.1_FL_2D")


@pytest.fixture
def source(slide: Path) -> Iterator[VsiSource]:
    source = VsiSource(UPath(slide), None)
    yield source
    source.close()


class TestVsiSource:
    def test_supports_local_path(self, slide: Path):
        # Act
        supported = VsiSource.is_supported(slide)

        # Assert
        assert supported is True

    def test_does_not_support_non_local_fsspec_path(self, slide: Path):
        # The sidecar directory of .ets files is read as local files, so a slide
        # on a filesystem that is not local must be declined.

        # Act
        supported = VsiSource.is_supported(UPath(f"memory://{slide.as_posix()}"))

        # Assert
        assert supported is False

    def test_does_not_support_vsi_without_sidecar(self, tmp_path: Path):
        # Arrange
        without_sidecar = tmp_path.joinpath("slide.vsi")
        without_sidecar.touch()

        # Act
        supported = VsiSource.is_supported(without_sidecar)

        # Assert
        assert supported is False

    def test_levels_are_exactly_half_of_previous(self, source: VsiSource):
        # Levels that are not an exact factor two apart make viewers drift the
        # image at each zoom step, so the padding of the tile grid of a level
        # must not be included in its size.

        # Act
        levels = [
            source._create_level_image_data(level.index).image_size
            for level in source.pyramid_levels
        ]

        # Assert
        assert levels[0].width > levels[-1].width
        for level, next_level in zip(levels, levels[1:], strict=False):
            assert next_level == Size(
                math.ceil(level.width / 2),
                math.ceil(level.height / 2),
            )

    def test_level_size_fits_in_tile_grid(self, source: VsiSource):
        # Act
        image_data = [
            source._create_level_image_data(level.index)
            for level in source.pyramid_levels
        ]

        # Assert
        for level, level_image_data in zip(
            source.pyramid_levels, image_data, strict=True
        ):
            grid = source._ets.tiled_sizes[level.level] * source._ets.tile_size
            assert level_image_data.image_size.width <= grid.width
            assert level_image_data.image_size.height <= grid.height

    def test_level_tile_is_passed_through(self, source: VsiSource, slide: Path):
        # Arrange
        image_data = source._create_level_image_data(0)
        stacks = [
            EtsFile(path)
            for path in sorted(slide.parent.joinpath(f"_{slide.stem}_").glob("*/*.ets"))
        ]
        pyramid = max(stacks, key=lambda stack: stack.tiled_sizes[0].area)
        expected_tile = pyramid.get_tile(0, Point(0, 0))
        for stack in stacks:
            stack.close()

        # Act
        tile = image_data.get_encoded_tile(Point(0, 0), 0.0, "0")

        # Assert
        assert image_data.transfer_syntax == JPEG2000
        assert image_data.transcoder is None
        assert tile.startswith(J2K_SOC_SIZ)
        assert tile == expected_tile

    def test_tile_size(self, source: VsiSource):
        # Act
        tile_size = source._create_level_image_data(0).tile_size

        # Assert
        assert tile_size == Size(512, 512)

    def test_get_any_tile_returns_a_stored_tile(self, source: VsiSource):
        # The tile format is sniffed from any present tile, not the corner (0, 0),
        # as a level can be sparse - the scanner omits tiles outside the scanned
        # region. On a dense slide the first present tile is the corner.

        # Act
        any_tile = source._ets.get_any_tile(0)

        # Assert
        assert any_tile is not None
        assert any_tile == source._ets.get_tile(0, Point(0, 0))

    def test_photometric_interpretation_is_ybr_ict(self, source: VsiSource):
        # The tiles use the irreversible colour transform, which DICOM signals as
        # YBR_ICT. Signalling RGB instead decodes with wrong colours.

        # Act
        photometric_interpretation = source._create_level_image_data(
            0
        ).photometric_interpretation

        # Assert
        assert photometric_interpretation == "YBR_ICT"

    def test_jpeg_tile_is_passed_through(self, jpeg_slide: Path):
        # Olympus also stores JPEG tiles, which are passed through as baseline
        # JPEG with the subsampled photometric interpretation DICOM requires.

        # Arrange
        source = VsiSource(UPath(jpeg_slide), None)

        # Act
        image_data = source._create_level_image_data(0)
        tile = image_data.get_encoded_tile(Point(0, 0), 0.0, "0")

        # Assert
        assert image_data.transfer_syntax == JPEGBaseline8Bit
        assert image_data.transcoder is None
        assert image_data.photometric_interpretation == "YBR_FULL_422"
        assert tile.startswith(JPEG_SOI)
        source.close()

    def test_image_size_excludes_tile_grid_padding_when_recorded(
        self, jpeg_slide: Path
    ):
        # The tail of the ETS header records the unpadded image size, which the
        # older writer of the OS-* slides leaves zero.

        # Arrange
        source = VsiSource(UPath(jpeg_slide), None)

        # Act
        image_size = source._create_level_image_data(0).image_size

        # Assert
        grid = source._ets.tiled_sizes[0] * source._ets.tile_size
        assert source._ets.image_size is not None
        assert image_size == source._ets.image_size
        assert image_size.width < grid.width
        assert image_size.height < grid.height
        source.close()

    def test_image_names(self, slide: Path):
        # Act
        images = VsiImage.read_all(slide)

        # Assert
        assert [image.name for image in images] == ["Overview", "20x"]

    def test_image_position_and_pixel_spacing(self, jpeg_slide: Path):
        # The metadata blocks give each image its position on the slide (tag
        # 2018) and its physical pixel size (2019), both in the unit named by
        # tag 2020.

        # Act
        images = {image.name: image for image in VsiImage.read_all(jpeg_slide)}

        # Assert
        area = images["20x_BF_01"]
        assert area.origin is not None
        assert area.origin.x == pytest.approx(37.100, abs=0.001)
        assert area.origin.y == pytest.approx(4.614, abs=0.001)
        assert area.pixel_spacing is not None
        assert area.pixel_spacing.width == pytest.approx(0.000274, abs=0.000001)
        assert images["20x_BF_02"].origin != area.origin

    def test_multiple_scanned_areas_are_refused(self, jpeg_slide: Path):
        # A slide with several scanned areas holds several pyramids; converting more
        # than one is not supported, so assembling the pyramid levels must fail loudly.
        # The areas stay individually readable - the tile and label/overview tests on
        # this same slide still construct the source and read from it.

        # Arrange
        source = VsiSource(UPath(jpeg_slide), None)

        # Act & Assert - Image_V4.1_BF has two scanned areas...
        assert len(source._areas) == 2
        with pytest.raises(NotImplementedError):
            _ = source.pyramid_levels  # ...so building the conversion is refused
        source.close()

    def test_label_and_overview_are_read_from_named_stacks(self, jpeg_slide: Path):
        # The label and macro are pyramids of their own in the sidecar, named by
        # the VSI metadata blocks.

        # Arrange
        source = VsiSource(UPath(jpeg_slide), None)

        # Act
        label = source._create_label_image_data()
        overview = source._create_overview_image_data()

        # Assert
        assert label is not None
        assert overview is not None
        assert label.transfer_syntax == JPEGBaseline8Bit
        assert label.transcoder is None
        assert label.image_size.width >= 1024
        assert overview.image_size.width >= 1024
        assert overview.image_size.width > overview.image_size.height
        source.close()

    def test_slide_without_label_has_no_label_image(self, source: VsiSource):
        # OS-1 is scanned without a label image, but does have an overview.

        # Act
        label = source._create_label_image_data()
        overview = source._create_overview_image_data()

        # Assert
        assert label is None
        assert overview is not None

    def test_associated_stacks_do_not_become_scanned_areas(self, source: VsiSource):
        # Associated images (overview, label, and any thumbnail) must never be
        # converted as a volume pyramid. OS-1 has an overview stack alongside its
        # single 20x area; the overview must stay out of the scanned areas and the
        # volume levels. This guards the class of bug where associated content
        # leaks into the pyramids — e.g. a non-square thumbnail series, or a
        # name/stack misalignment on a label-dropped production slide.

        # Act
        area_names = {name for _, name, _, _ in source._area_levels}

        # Assert
        assert OVERVIEW_NAME in source._stacks  # OS-1 does have an overview...
        assert OVERVIEW_NAME not in source._areas  # ...but it is not a scanned area
        assert LABEL_NAME not in source._areas
        assert OVERVIEW_NAME not in area_names
        assert area_names == set(source._areas)

    def test_multi_channel_slide_is_refused(self, multi_channel_slide: Path):
        # Channels, focal planes and time points appear as extra dimensions in
        # the tile index, none of which are mapped to DICOM yet. Converting one
        # of their tiles as if it was the whole image would be silently wrong.

        # Act & Assert
        with pytest.raises(NotImplementedError):
            VsiSource(UPath(multi_channel_slide), None)

    def test_slide_identifier(self, slide: Path):
        # OS-1 states its slide barcode in tag 2061.

        # Act
        identifier = VsiImage.read_slide_identifier(slide)

        # Assert
        assert identifier == "04050732B0018S"

    def test_slide_identifier_is_confidential(self, slide: Path):
        # The slide barcode identifies the specimen, so it must be dropped when
        # confidential metadata is excluded.

        # Arrange
        included = VsiSource(UPath(slide), None, include_confidential=True)
        excluded = VsiSource(UPath(slide), None, include_confidential=False)

        # Act & Assert
        assert included.metadata.slide.identifier == "04050732B0018S"
        assert excluded.metadata.slide.identifier is None
        included.close()
        excluded.close()

    def test_pixel_spacing(self, source: VsiSource):
        # The base pixel spacing is derived from the physical size of the sample
        # mask image in the .vsi and the Exif size of the scanned area.

        # Act
        pixel_spacing = source.metadata.pyramid.image.pixel_spacing

        # Assert
        assert pixel_spacing is not None
        assert pixel_spacing.width == pytest.approx(0.000346, abs=0.000001)
        assert pixel_spacing.height == pytest.approx(0.000346, abs=0.000001)
