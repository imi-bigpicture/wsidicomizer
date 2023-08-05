#    Copyright 2023 SECTRA AB
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

from typing import Optional, Sequence

import pytest

from wsidicomizer.dicomizer_source import DicomizerSource


@pytest.mark.unittest
class TestWsiDicomizer:
    @pytest.mark.parametrize(
        ["level", "present_levels", "include_indices"],
        [(0, [0, 1, 2], None), (1, [0, 1, 2], None), (2, [0, 1, 2], None)],
    )
    def test_is_included_level_include_indices_is_none(
        self,
        level: int,
        present_levels: Sequence[int],
        include_indices: Optional[Sequence[int]],
    ):
        # Arrange

        # Act
        is_included = DicomizerSource._is_included_level(
            level, present_levels, include_indices
        )

        # Assert
        assert is_included

    @pytest.mark.parametrize(
        ["level", "present_levels", "include_indices"],
        [
            (-1, [0, 1, 2], None),
            (3, [0, 1, 2], None),
            (0, [], None),
            (-1, [0, 1, 2], [0, 1, 2]),
            (3, [0, 1, 2], [0, 1, 2]),
            (0, [], [0, 1, 2]),
        ],
    )
    def test_is_included_level_level_not_in_present_levels_is_none(
        self,
        level: int,
        present_levels: Sequence[int],
        include_indices: Optional[Sequence[int]],
    ):
        # Arrange

        # Act
        is_included = DicomizerSource._is_included_level(
            level, present_levels, include_indices
        )

        # Assert
        assert not is_included

    @pytest.mark.parametrize(
        ["level", "present_levels", "include_indices"],
        [
            (0, [0, 1, 2], [0, 1, 2]),
            (1, [0, 1, 2], [0, 1, 2]),
            (2, [0, 1, 2], [0, 1, 2]),
            (0, [0, 1, 2], [0]),
            (1, [0, 1, 2], [1]),
            (2, [0, 1, 2], [2]),
            (0, [0, 1, 2], [-3]),
            (1, [0, 1, 2], [-2]),
            (2, [0, 1, 2], [-1]),
            (0, [0, 1, 2], [0, 10, -10]),
        ],
    )
    def test_is_included_level_level_index_is_in_included_indices(
        self, level: int, present_levels: Sequence[int], include_indices: Sequence[int]
    ):
        # Arrange

        # Act
        is_included = DicomizerSource._is_included_level(
            level, present_levels, include_indices
        )

        # Assert
        assert is_included

    @pytest.mark.parametrize(
        ["level", "present_levels", "include_indices"],
        [
            (0, [0, 1, 2], [1, 2]),
            (1, [0, 1, 2], [0, 2]),
            (2, [0, 1, 2], [0, 1]),
            (0, [0, 1, 2], [1]),
            (1, [0, 1, 2], [2]),
            (2, [0, 1, 2], [0]),
            (0, [0, 1, 2], [-1]),
            (1, [0, 1, 2], [-1]),
            (2, [0, 1, 2], [-2]),
            (0, [0, 1, 2], [1, 10, -10]),
            (0, [0, 1, 2], []),
        ],
    )
    def test_is_included_level_level_index_is_not_in_included_indices(
        self, level: int, present_levels: Sequence[int], include_indices: Sequence[int]
    ):
        # Arrange

        # Act
        is_included = DicomizerSource._is_included_level(
            level, present_levels, include_indices
        )

        # Assert
        assert not is_included
