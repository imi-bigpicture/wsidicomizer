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

"""Tests that conversion follows a source's preference for regenerating the
pyramid unless the caller decides."""

from typing import Any

import pytest

from wsidicomizer import WsiDicomizer


class FakeWsi:
    def __init__(self, prefer_regenerated_pyramid: bool):
        self._prefer_regenerated_pyramid = prefer_regenerated_pyramid
        self.save_kwargs: dict[str, Any] = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def save(self, *args, **kwargs):
        self.save_kwargs = kwargs
        return []


@pytest.mark.parametrize(
    ["prefer", "regenerate_pyramid", "include_levels", "expected"],
    [
        (True, None, None, True),
        (False, None, None, False),
        (True, None, [0, 1], False),
        (True, False, None, False),
        (False, True, None, True),
    ],
)
def test_convert_follows_source_preference(
    monkeypatch: pytest.MonkeyPatch,
    prefer: bool,
    regenerate_pyramid: bool | None,
    include_levels: list[int] | None,
    expected: bool,
):
    # Arrange
    wsi = FakeWsi(prefer)
    monkeypatch.setattr(WsiDicomizer, "open", classmethod(lambda cls, *a, **k: wsi))

    # Act
    WsiDicomizer.convert(
        "slide",
        "output",
        regenerate_pyramid=regenerate_pyramid,
        include_levels=include_levels,
    )

    # Assert
    assert wsi.save_kwargs["regenerate_pyramid"] is expected
