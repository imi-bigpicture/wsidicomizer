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

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from upath import UPath
from wsidicom.geometry import Point, Region, Size

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.errors import SourceNotSupportedError
from wsidicomizer.sources.mirax import MiraxSource
from wsidicomizer.sources.mirax.mirax_image_data import (
    MiraxFluorescenceLevelImageData,
    MiraxLevelImageData,
)
from wsidicomizer.sources.mirax.reader import MiraxReader


@pytest.fixture
def source(mirax_path: Path) -> Iterator[MiraxSource]:
    mirax_source = MiraxSource(UPath(mirax_path), None)
    yield mirax_source
    mirax_source.close()


@pytest.fixture
def fluorescence_source(fluorescence_mirax_path: Path) -> Iterator[MiraxSource]:
    mirax_source = MiraxSource(UPath(fluorescence_mirax_path), None)
    yield mirax_source
    mirax_source.close()


class TestMiraxSource:
    def test_is_supported(self, mirax_path: Path):
        # Act / Assert
        assert MiraxSource.is_supported(mirax_path)
        assert not MiraxSource.is_supported(mirax_path.with_suffix(".svs"))

    def test_reduced_pyramid_refused_when_created(self, reduced_mirax_path: Path):
        # Arrange

        # Act / Assert - a reduced pyramid is a MIRAX slide, but creating the source
        # refuses it, so that another source (OpenSlide) is tried
        assert MiraxSource.is_supported(reduced_mirax_path)
        with pytest.raises(SourceNotSupportedError):
            MiraxSource(UPath(reduced_mirax_path), None)

    def test_failed_init_closes_reader(
        self, mirax_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        closed: list[bool] = []

        def failing_init(*args, **kwargs):
            raise RuntimeError("failed")

        monkeypatch.setattr(DicomizerSource, "__init__", failing_init)
        close = MiraxReader.close

        def recording_close(self: MiraxReader) -> None:
            closed.append(True)
            close(self)

        monkeypatch.setattr(MiraxReader, "close", recording_close)

        # Act
        with pytest.raises(RuntimeError):
            MiraxSource(UPath(mirax_path), None)

        # Assert
        assert closed

    def test_metadata(self, source: MiraxSource):
        # Act
        metadata = source.base_metadata
        image = metadata.pyramid.image

        # Assert
        assert image.pixel_spacing is not None
        assert image.image_coordinate_system is not None
        assert image.image_coordinate_system.rotation == 270.0  # WsiFormat.MIRAX
        # MIRAX-specific fields the openslide property model doesn't carry
        assert metadata.equipment.manufacturer == "3DHISTECH"
        assert metadata.equipment.software_versions is not None
        assert image.acquisition_datetime is not None

    def test_image_origin_is_tissue_bounds(self, source: MiraxSource):
        # Arrange - CMU-1's tissue bounding box starts at level-0 (9919, 89420)
        # of the scan grid, 0.2325 um/pixel
        expected_offset = Point(9919, 89420)

        # Act
        image = source.base_metadata.pyramid.image

        # Assert
        assert source._mrxs.bounds_offset == expected_offset
        assert image.image_coordinate_system is not None
        assert image.image_coordinate_system.origin.x == pytest.approx(2.3061675)
        assert image.image_coordinate_system.origin.y == pytest.approx(20.79015)

    def test_thumbnail_cropped_to_tissue_bounds(self, source: MiraxSource):
        # Arrange - the 854x1724 SlidePreview covers the 109240x220696 scan grid
        assert source._mrxs.scan_dimensions == Size(109240, 220696)

        # Act
        thumbnail = source._create_thumbnail_image_data()

        # Assert - cropped to the 68315x94972 bounds at downsample ~128
        assert thumbnail is not None
        assert thumbnail.image_size.to_tuple() == (534, 742)

    def test_level_reads_rgb_tissue_and_fill_margin(self, source: MiraxSource):
        # Arrange
        image_data = source._create_level_image_data(0)
        assert isinstance(image_data, MiraxLevelImageData)

        # Act
        tissue = image_data.get_decoded_region(
            Region(Point(15360, 40448), Size(512, 512)), 0.0, "1"
        )
        margin = image_data.get_decoded_region(  # no tiles
            Region(Point(0, 0), Size(64, 64)), 0.0, "1"
        )

        # Assert
        assert tissue.dtype == np.uint8 and tissue.shape[2] == 3
        assert tissue[:, :, 1].min() < 255, "expected tissue"
        assert (margin == 255).all(), "expected fill margin"

    def test_level_has_no_fill_seams_between_tiles(self, source: MiraxSource):
        # Arrange - a tissue window crossing seams between the tiles of one camera
        # photo and between photos
        image_data = source._create_level_image_data(0)
        assert isinstance(image_data, MiraxLevelImageData)
        fill = np.array(image_data.blank_color, dtype=np.uint8)

        # Act
        region = image_data.get_decoded_region(
            Region(Point(15360, 40448), Size(2048, 2048)), 0.0, "1"
        )

        # Assert - no row or column is fill where both its neighbours are tissue
        is_fill = (region == fill).all(axis=2)
        between_tissue_rows = is_fill[1:-1] & ~is_fill[:-2] & ~is_fill[2:]
        between_tissue_columns = is_fill[:, 1:-1] & ~is_fill[:, :-2] & ~is_fill[:, 2:]
        assert between_tissue_rows.mean(axis=1).max() < 0.1
        assert between_tissue_columns.mean(axis=0).max() < 0.1

    def test_fluorescence_channels_are_bands_of_packed_tiles(
        self, fluorescence_source: MiraxSource
    ):
        # Arrange - the packed tiles composed as one RGB level
        image_data = fluorescence_source._create_level_image_data(0)
        assert isinstance(image_data, MiraxFluorescenceLevelImageData)
        packed = MiraxLevelImageData(
            fluorescence_source._mrxs,
            fluorescence_source.metadata.pyramid.image,
            None,
            fluorescence_source._encoder,
            fluorescence_source._decoded_frame_cache,
        )
        size = image_data.image_size
        region = Region(Point(size.width // 3, size.height // 3), Size(256, 256))
        packed_region = packed.get_decoded_region(region, 0.0, "1")

        # Act / Assert - each channel equals its band of the packed region
        for path, channel in zip(
            image_data.optical_paths, fluorescence_source._mrxs.channels, strict=True
        ):
            channel_region = image_data.get_decoded_region(region, 0.0, path)
            assert np.array_equal(channel_region, packed_region[:, :, channel.band])

    def test_level_image_data_reads_rgb_tile(self, source: MiraxSource):
        # Arrange
        image_data = source._create_level_image_data(0)

        # Act
        tile = image_data.get_decoded_tile(Point(30, 79), 0.0, "1")

        # Assert
        assert image_data.samples_per_pixel == 3
        assert tile.shape == (
            image_data.tile_size.height,
            image_data.tile_size.width,
            3,
        )

    def test_fluorescence_channels_as_grayscale_optical_paths(
        self, fluorescence_source: MiraxSource
    ):
        # Act
        image_data = fluorescence_source._create_level_image_data(0)
        optical_paths = fluorescence_source.base_metadata.pyramid.optical_paths
        path = image_data.optical_paths[0]
        tile = image_data.get_decoded_tile(Point(0, 0), 0.0, path)

        # Assert - each channel is its own grayscale MONOCHROME2 optical path
        assert image_data.samples_per_pixel == 1
        assert image_data.photometric_interpretation == "MONOCHROME2"
        assert len(image_data.optical_paths) == 3
        assert [op.identifier for op in optical_paths] == image_data.optical_paths
        assert tile.ndim == 2
        assert tile.dtype == np.uint8

    def test_fluorescence_blank_tile_is_shared_fill_frame(
        self, fluorescence_source: MiraxSource
    ):
        # Arrange - find a tile that is all the slide's stated fill value
        image_data = fluorescence_source._create_level_image_data(0)
        assert isinstance(image_data, MiraxFluorescenceLevelImageData)
        path = image_data.optical_paths[0]
        fill = image_data._channel_fill(path)
        blank_point = next(
            point
            for point in (
                Point(x, y)
                for y in range(image_data.tiled_size.height)
                for x in range(image_data.tiled_size.width)
            )
            if (image_data.get_decoded_tile(point, 0.0, path) == fill).all()
        )

        # Act
        encoded = image_data.get_encoded_tile(blank_point, 0.0, path)

        # Assert - the blank is encoded once and reused, not re-encoded per tile
        assert encoded is image_data._get_blank_encoded_frame(
            image_data.tile_size, fill
        )

    def test_png_fluorescence_channels(self, png_fluorescence_mirax_path: Path):
        # Arrange
        source = MiraxSource(UPath(png_fluorescence_mirax_path), None)

        # Act
        image_data = source._create_level_image_data(0)
        path = image_data.optical_paths[0]
        tile = image_data.get_decoded_tile(Point(0, 0), 0.0, path)

        # Assert - 8-bit PNG tiles split into grayscale channels
        assert image_data.bits == 8
        assert image_data.samples_per_pixel == 1
        assert len(image_data.optical_paths) == 3
        assert tile.ndim == 2
        assert tile.dtype == np.uint8
        source.close()

    def test_16bit_fluorescence_channels(self, high_bit_fluorescence_mirax_path: Path):
        # Arrange
        source = MiraxSource(UPath(high_bit_fluorescence_mirax_path), None)

        # Act
        image_data = source._create_level_image_data(0)
        path = image_data.optical_paths[0]
        tile = image_data.get_decoded_tile(Point(0, 0), 0.0, path)
        encoded = image_data.get_encoded_tile(Point(0, 0), 0.0, path)

        # Assert - 16-bit JPEG-XR tiles split into 16-bit MONOCHROME2 channels
        assert image_data.bits == 16
        assert image_data.samples_per_pixel == 1
        assert image_data.photometric_interpretation == "MONOCHROME2"
        assert tile.ndim == 2
        assert tile.dtype == np.uint16
        assert len(encoded) > 0
        source.close()
