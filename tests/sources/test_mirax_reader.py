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

"""Tests for the MIRAX reader itself (placement, tiles, channels)."""

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from wsidicomizer.sources.mirax.reader import MiraxReader


@pytest.fixture
def reader(mirax_path: Path) -> Iterator[MiraxReader]:
    slide = MiraxReader(mirax_path)
    yield slide
    slide.close()


class TestMiraxReader:
    def test_levels_roughly_halve(self, reader: MiraxReader):
        # Act
        dimensions = reader.level_dimensions

        # Assert
        assert reader.level_count == 10
        for level in range(1, reader.level_count):
            width_coarse, height_coarse = dimensions[level - 1]
            width_fine, height_fine = dimensions[level]
            assert 1.5 < width_coarse / width_fine < 2.5, level
            assert 1.5 < height_coarse / height_fine < 2.5, level

    def test_associated_image_sizes_match_slidedat(self, reader: MiraxReader):
        # Act
        associated = reader.associated_images

        # Assert - decoded sizes must match Slidedat.ini (nonhierarchical parsing)
        assert associated["thumbnail"].size == (854, 1724)  # SlidePreview
        assert associated["macro"].size == (563, 1128)  # SlideThumbnail
        assert associated["label"].size == (615, 462)  # SlideBarcode

    def test_reads_rgb_tissue_and_fill_margin(self, reader: MiraxReader):
        # Act
        tissue = reader.read_region(6, (0, 0), reader.level_dimensions[6])
        margin = reader.read_region(0, (0, 0), (64, 64))  # top-left, no tiles

        # Assert
        assert tissue.dtype == np.uint8 and tissue.shape[2] == 3
        assert tissue[:, :, 1].min() < 255, "expected tissue"
        assert (margin == 255).all(), "expected fill margin"

    def test_brightfield_has_mpp_and_no_channels(self, reader: MiraxReader):
        # Act
        mpp = reader.slidedat.mpp

        # Assert
        assert mpp is not None and mpp[0] > 0 and mpp[1] > 0
        assert reader.channels == []

    def test_overlap_is_removed(self, reader: MiraxReader):
        # Arrange - a naive abutting layout ignores the per-photo overlap
        columns = {column for column, _ in reader._index.levels[0]}
        abutting_width = (max(columns) - min(columns) + 1) * reader._meta.tile_size[0]

        # Act
        width = reader.dimensions[0]

        # Assert
        assert reader._index.position_buffer is not None
        assert width < abutting_width

    def test_read_regions_matches_read_region(self, reader: MiraxReader):
        # Arrange
        step = 512
        locations = [
            (15000 + i * step, 40000 + j * step) for j in range(3) for i in range(3)
        ]

        # Act
        batch = reader.read_regions(0, locations, (step, step))

        # Assert
        for location, region in zip(locations, batch, strict=True):
            reference = reader.read_region(0, location, (step, step))
            assert np.array_equal(region, reference), location

    def test_get_tile_matches_read_region(self, reader: MiraxReader):
        # Arrange
        step = 512

        # Act
        tile = reader.get_tile(0, 30, 79, step)  # == read_region at (15360, 40448)

        # Assert
        reference = reader.read_region(0, (30 * step, 79 * step), (step, step))
        assert np.array_equal(tile, reference)

    def test_blank_tiles_are_independent(self, reader: MiraxReader):
        # Arrange - an empty grid position returns a fresh fill tile
        blank = reader.get_tile(0, 0, 0, 512)

        # Act - mutate one blank tile
        blank[:] = 7

        # Assert - the shared fill template is not corrupted
        assert not (reader.get_tile(0, 0, 0, 512) == 7).all()

    def test_rejects_reduced_pyramid(self, reduced_mirax_path: Path):
        # Act / Assert - a truncated pyramid is detected and rejected
        with pytest.raises(NotImplementedError):
            MiraxReader(reduced_mirax_path)

    def test_fluorescence_channels_split_to_bands(self, fluorescence_mirax_path: Path):
        # Arrange
        reader = MiraxReader(fluorescence_mirax_path)
        level = min(3, reader.level_count - 1)
        width, height = reader.level_dimensions[level]
        location = (width // 3, height // 3)
        region = reader.read_region(level, location, (256, 256))

        # Act / Assert - each channel equals its packed band of the region
        assert reader.channels, "expected fluorescence channels"
        for index, channel in enumerate(reader.channels):
            channel_array = reader.read_channel(level, location, (256, 256), index)
            assert np.array_equal(channel_array, region[:, :, channel.band]), channel
        reader.close()
