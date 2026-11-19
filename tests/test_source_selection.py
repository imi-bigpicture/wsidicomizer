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

"""Tests for trying the sources of a file's format in turn (no slide needed)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from wsidicomizer import SourceNotSupportedError, WsiDicomizer


class Opened(Exception):
    """Raised by a source that would have opened the file, ending the open."""


class RefusingSource:
    """A source of the file's format that refuses the file's variant."""

    created: list[str] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.created.append(type(self).__name__)
        raise SourceNotSupportedError("variant not read")


class OpeningSource(RefusingSource):
    """A source that reads the file."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.created.append(type(self).__name__)
        raise Opened()


class FailingSource(RefusingSource):
    """A source that fails reading a broken file."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.created.append(type(self).__name__)
        raise RuntimeError("broken file")


@pytest.fixture
def candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., list[str]]:
    def set_candidates(*sources: type) -> list[str]:
        created: list[str] = []
        RefusingSource.created = created
        monkeypatch.setattr(
            WsiDicomizer,
            "_select_sources",
            staticmethod(lambda *args, **kwargs: list(sources)),
        )
        return created

    return set_candidates


@pytest.mark.unittest
class TestSourceSelection:
    def test_refused_file_is_tried_with_next_source(
        self, candidates: Callable[..., list[str]]
    ):
        # Arrange
        created = candidates(RefusingSource, OpeningSource)

        # Act / Assert
        with pytest.raises(Opened):
            WsiDicomizer.open("slide.mrxs")
        assert created == ["RefusingSource", "OpeningSource"]

    def test_file_refused_by_every_source_is_not_supported(
        self, candidates: Callable[..., list[str]]
    ):
        # Arrange
        candidates(RefusingSource, RefusingSource)

        # Act / Assert
        with pytest.raises(SourceNotSupportedError) as raised:
            WsiDicomizer.open("slide.mrxs")
        assert isinstance(raised.value.__cause__, SourceNotSupportedError)

    def test_error_other_than_refusal_is_raised(
        self, candidates: Callable[..., list[str]]
    ):
        # Arrange
        created = candidates(FailingSource, OpeningSource)

        # Act / Assert - a broken file reports its error instead of moving on
        with pytest.raises(RuntimeError, match="broken file"):
            WsiDicomizer.open("slide.mrxs")
        assert created == ["FailingSource"]

    def test_file_of_no_source_format_is_not_supported(self, tmp_path: Path):
        # Arrange
        path = tmp_path / "slide.unknown"
        path.write_bytes(b"not a slide")

        # Act / Assert
        with pytest.raises(SourceNotSupportedError):
            WsiDicomizer.open(path)
