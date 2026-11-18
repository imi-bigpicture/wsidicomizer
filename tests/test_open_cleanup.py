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

"""Files opened by a source are closed when opening fails."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from upath import UPath

from wsidicomizer import WsiDicomizer
from wsidicomizer.sources.opentile import opentile_source
from wsidicomizer.sources.tiffslide import tiffslide_source


class RefusedSource:
    """A source that opens, but whose levels the WsiDicomizer refuses when built."""

    closed = False

    def __init__(self, *args: Any, **kwargs: Any):
        type(self).closed = False

    @staticmethod
    def is_supported(
        path: str | Path | UPath, file_options: dict[str, Any] | None = None
    ) -> bool:
        return True

    @property
    def level_instances(self) -> list[Any]:
        raise NotImplementedError("2 pyramids")

    def close(self) -> None:
        type(self).closed = True


def fail(*args: Any, **kwargs: Any) -> None:
    raise ValueError("bad metadata")


@pytest.mark.unittest
class TestOpenCleanup:
    def test_open_closes_source_when_building_fails(self, tmp_path: Path):
        # Arrange

        # Act
        with pytest.raises(NotImplementedError):
            WsiDicomizer.open(
                tmp_path / "slide.svs",
                preferred_source=RefusedSource,  # pyright: ignore[reportArgumentType]
            )

        # Assert
        assert RefusedSource.closed

    def test_opentile_source_closes_tiler_when_init_fails(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        # Arrange
        closed: list[bool] = []
        tiler = SimpleNamespace(
            format=SimpleNamespace(name="SVS"),
            metadata=None,
            labels=[],
            overviews=[],
            icc_profile=None,
            close=lambda: closed.append(True),
        )
        monkeypatch.setattr(
            opentile_source.OpenTile, "open", lambda *args, **kwargs: tiler
        )
        monkeypatch.setattr(opentile_source, "OpenTileMetadata", fail)
        monkeypatch.setattr(opentile_source.OpenTileSource, "_volume_imaged_size", None)

        # Act
        with pytest.raises(ValueError):
            opentile_source.OpenTileSource(UPath(tmp_path / "slide.svs"), None)

        # Assert
        assert closed == [True]

    def test_tiffslide_source_closes_slide_when_init_fails(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        # Arrange
        closed: list[bool] = []
        slide = SimpleNamespace(
            properties={},
            level_downsamples=[1.0],
            level_dimensions=[(256, 256)],
            associated_images={},
            color_profile=None,
            close=lambda: closed.append(True),
        )
        monkeypatch.setattr(
            tiffslide_source, "TiffSlide", lambda *args, **kwargs: slide
        )
        monkeypatch.setattr(tiffslide_source, "OpenSlideLikeMetadata", fail)

        # Act
        with pytest.raises(ValueError):
            tiffslide_source.TiffSlideSource(UPath(tmp_path / "slide.svs"), None)

        # Assert
        assert closed == [True]
