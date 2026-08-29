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

"""Tests for mapping the levels of an openslide-like file to pyramid indices."""

from collections.abc import Sequence

import pytest

from wsidicomizer.sources.openslide_like.openslide_like_source import (
    OpenSlideLikeSource,
)


@pytest.mark.unittest
class TestMapPyramidLevels:
    @pytest.mark.parametrize(
        ("level_downsamples", "expected"),
        [
            ([1.0, 2.0, 4.0, 8.0], {0: 0, 1: 1, 2: 2, 3: 3}),
            ([1.0, 4.0, 16.0, 32.0], {0: 0, 2: 1, 4: 2, 5: 3}),
            ([1.0, 3.0, 9.0], {0: 0, 2: 1, 3: 2}),
        ],
    )
    def test_maps_each_level_to_its_nearest_index(
        self, level_downsamples: Sequence[float], expected: dict[int, int]
    ):
        # Act
        levels = OpenSlideLikeSource._map_pyramid_levels(level_downsamples)

        # Assert
        assert {key[0]: index for key, index in levels.items()} == expected

    def test_colliding_levels_are_logged(self, caplog: pytest.LogCaptureFixture):
        """Several levels can map to the same index, e.g. a fluorescence qptiff
        whose levels hold one same-sized plane per channel. Only one of them can
        be written, and the rest must not disappear without a word."""

        # Arrange
        level_downsamples = [1.0, 2.0, 2.0, 2.0]

        # Act
        with caplog.at_level("WARNING"):
            levels = OpenSlideLikeSource._map_pyramid_levels(level_downsamples)

        # Assert
        assert len(levels) == 2
        assert caplog.text.count("map to pyramid index") == 2
