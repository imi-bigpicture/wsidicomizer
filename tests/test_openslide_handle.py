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

"""Tests for the OpenSlide handle reopen-on-poison recovery (issue #146)."""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from decoy import Decoy, matchers
from openslide import OpenSlide
from openslide.lowlevel import _OpenSlide

import wsidicomizer.extras.openslide.openslide_handle as module
from wsidicomizer.config import settings
from wsidicomizer.extras.openslide.openslide import OpenSlideError
from wsidicomizer.extras.openslide.openslide_handle import OpenSlideHandle

ReadRegion = Callable[..., None]

ERROR = "Not a JPEG file: starts with 0x00 0x00"
ANY = matchers.Anything()


def read_region_signature(
    osr: object, buffer: object, x: int, y: int, level: int, width: int, height: int
) -> None:
    """The signature decoy specs the _read_region mock against."""


def stub_read_region(read_region: ReadRegion) -> None:
    """A rehearsal matching any _read_region call (the buffer pointer varies)."""
    return read_region(ANY, ANY, ANY, ANY, ANY, ANY, ANY)


def read(handle: OpenSlideHandle) -> np.ndarray | None:
    return handle.read(0, 0, 0, 1, 1)


@pytest.fixture
def slides(decoy: Decoy, monkeypatch: pytest.MonkeyPatch) -> list[OpenSlide]:
    """Patch OpenSlide so each open returns a fresh mock with a distinct ``_osr``.
    The returned list holds the mocks in open order (index 0 is the first handle)."""
    created: list[OpenSlide] = []

    def factory(filepath: Path) -> OpenSlide:
        slide = decoy.mock(cls=OpenSlide)
        osr = object()
        decoy.when(slide._osr).then_return(cast(_OpenSlide, osr))
        created.append(slide)
        return slide

    monkeypatch.setattr(module, "OpenSlide", factory)
    return created


@pytest.fixture
def read_region(decoy: Decoy, monkeypatch: pytest.MonkeyPatch) -> ReadRegion:
    mock = cast(ReadRegion, decoy.mock(func=read_region_signature))
    monkeypatch.setattr(module, "_read_region", mock)
    return mock


@pytest.fixture
def handle(slides: list[OpenSlide]) -> OpenSlideHandle:
    # Depends on `slides` for its side effect: it patches module.OpenSlide, which
    # the constructor calls. (Reads also need the `read_region` patch, but tests
    # that read request that fixture themselves.)
    return OpenSlideHandle(Path("fake.svs"))


class TestOpenSlideHandleRead:
    def test_successful_read_does_not_reopen(
        self,
        decoy: Decoy,
        handle: OpenSlideHandle,
        read_region: ReadRegion,
        slides: list[OpenSlide],
    ) -> None:
        # Arrange
        decoy.when(stub_read_region(read_region)).then_return(None)
        initial_generation = handle._generation

        # Act
        result = read(handle)

        # Assert
        assert result is not None
        assert handle._generation == initial_generation
        assert handle._unreadable_regions == 0
        decoy.verify(slides[0].close(), times=0)

    def test_poisoned_read_recovers_on_reopen(
        self,
        decoy: Decoy,
        handle: OpenSlideHandle,
        read_region: ReadRegion,
        slides: list[OpenSlide],
    ) -> None:
        # Arrange: reads on the first (poisoned) handle fail; reads on the reopened
        # handle are left unstubbed, so decoy returns None (success). The first
        # handle is a victim — its region is fine once read on a fresh handle.
        decoy.when(
            read_region(slides[0]._osr, ANY, ANY, ANY, ANY, ANY, ANY)
        ).then_raise(OpenSlideError(ERROR))
        generation = handle._generation

        # Act
        result = read(handle)

        # Assert: the poisoned handle was reopened once and the retry succeeded.
        assert result is not None
        assert handle._generation == generation + 1
        assert handle._unreadable_regions == 0
        decoy.verify(slides[0].close(), times=1)

    def test_unreadable_region_is_blanked(
        self, decoy: Decoy, handle: OpenSlideHandle, read_region: ReadRegion
    ) -> None:
        # Arrange: the read always fails (genuinely unreadable region).
        decoy.when(stub_read_region(read_region)).then_raise(OpenSlideError(ERROR))

        # Act
        result = read(handle)

        # Assert
        assert result is None
        assert handle._unreadable_regions == 1

    def test_later_victim_of_same_poisoning_skips_reopen(
        self,
        decoy: Decoy,
        handle: OpenSlideHandle,
        read_region: ReadRegion,
        slides: list[OpenSlide],
    ) -> None:
        # Arrange: another thread already reopened after this read's snapshot
        # (generation advanced), and the retry succeeds.
        decoy.when(stub_read_region(read_region)).then_return(None)
        generation = handle._generation
        handle._generation += 1

        # Act: recover with the stale generation seen before the reopen.
        result = handle._recover(
            generation, np.empty((1, 1, 4), np.uint8), 0, 0, 0, 1, 1
        )

        # Assert: no extra reopen, just a retry on the already-fresh handle.
        assert result is True
        assert handle._generation == generation + 1
        decoy.verify(slides[0].close(), times=0)

    def test_skip_path_reopens_before_blanking_a_repoisoned_handle(
        self,
        decoy: Decoy,
        handle: OpenSlideHandle,
        read_region: ReadRegion,
        slides: list[OpenSlide],
    ) -> None:
        # Arrange: the skip-reopen path (generation already advanced), but the
        # current handle was re-poisoned in the gap between serialized recoveries —
        # reads on it fail, reads on the next reopened handle are unstubbed and
        # succeed. A good region must be reopened-and-retried here, never blanked
        # just because another thread's bad read poisoned the shared handle (#146).
        decoy.when(
            read_region(slides[0]._osr, ANY, ANY, ANY, ANY, ANY, ANY)
        ).then_raise(OpenSlideError(ERROR))
        generation = handle._generation
        handle._generation += 1

        # Act: recover with the stale generation seen before the reopen.
        result = handle._recover(
            generation, np.empty((1, 1, 4), np.uint8), 0, 0, 0, 1, 1
        )

        # Assert: the good region recovered on a fresh handle instead of blanking.
        assert result is True
        assert handle._unreadable_regions == 0
        decoy.verify(slides[0].close(), times=1)

    def test_aborts_when_unreadable_limit_exceeded(
        self,
        decoy: Decoy,
        handle: OpenSlideHandle,
        read_region: ReadRegion,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange
        monkeypatch.setattr(settings, "openslide_unreadable_region_limit", 2)
        decoy.when(stub_read_region(read_region)).then_raise(OpenSlideError(ERROR))

        # Act: blank up to the limit, then abort on the next.
        assert read(handle) is None
        assert read(handle) is None

        # Assert
        with pytest.raises(RuntimeError, match="corrupt or otherwise unreadable"):
            read(handle)

    def test_reopen_closes_the_old_handle(
        self,
        decoy: Decoy,
        handle: OpenSlideHandle,
        read_region: ReadRegion,
        slides: list[OpenSlide],
    ) -> None:
        # Arrange: a failed read drains readers, then reopens (closing the old
        # handle rather than leaking it).
        decoy.when(stub_read_region(read_region)).then_raise(OpenSlideError(ERROR))

        # Act
        read(handle)

        # Assert
        decoy.verify(slides[0].close(), times=1)

    def test_close_closes_current_handle(
        self, decoy: Decoy, handle: OpenSlideHandle, slides: list[OpenSlide]
    ) -> None:
        # Act
        handle.close()

        # Assert
        decoy.verify(slides[0].close(), times=1)

    def test_concurrent_poisoning_reopens_once_and_recovers_all_victims(
        self,
        decoy: Decoy,
        handle: OpenSlideHandle,
        slides: list[OpenSlide],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange: N threads read the initial handle concurrently, synced on a
        # barrier so they are genuinely in-flight together, then all fail. Reads on
        # any reopened handle succeed (its osr differs). This exercises the Condition
        # drain and the generation dedup under real contention.
        workers = 8
        poisoned_osr = handle._osr
        barrier = threading.Barrier(workers, timeout=10)

        def fake_read_region(osr: object, buffer: object, *rest: int) -> None:
            if osr is poisoned_osr:
                barrier.wait()  # all readers in-flight together, then poison
                raise OpenSlideError(ERROR)
            # reopened handle: succeeds (returns None)

        monkeypatch.setattr(module, "_read_region", fake_read_region)

        # Act
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(lambda _: read(handle), range(workers)))

        # Assert: every victim recovered, and the handle reopened exactly once
        # despite all workers observing the poisoning.
        assert all(result is not None for result in results)
        assert handle._generation == 1
        assert handle._unreadable_regions == 0
        decoy.verify(slides[0].close(), times=1)

    def test_concurrent_poisoning_blanks_only_the_corrupt_region(
        self,
        handle: OpenSlideHandle,
        slides: list[OpenSlide],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange: N threads read concurrently. One reads a genuinely corrupt
        # region (x == BAD_X) that fails even on a fresh handle; the rest are
        # victims that fail only on the poisoned handle. All sync on a barrier so
        # the first reads are in-flight together.
        workers = 8
        bad_x = 999
        poisoned_osr = handle._osr
        barrier = threading.Barrier(workers, timeout=10)

        def fake_read_region(osr: object, buffer: object, x: int, *rest: int) -> None:
            if osr is poisoned_osr:
                barrier.wait()  # all first reads in-flight, then all fail
                raise OpenSlideError(ERROR)
            if x == bad_x:  # genuinely corrupt region: fails on a fresh handle too
                raise OpenSlideError(ERROR)
            # victim on a fresh handle: succeeds (returns None)

        monkeypatch.setattr(module, "_read_region", fake_read_region)

        def worker(index: int) -> np.ndarray | None:
            x = bad_x if index == 0 else 0
            return handle.read(x, 0, 0, 1, 1)

        # Act
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(worker, range(workers)))

        # Assert: only the corrupt region is blanked; every victim recovered.
        assert results[0] is None
        assert all(result is not None for result in results[1:])
        assert handle._unreadable_regions == 1
        # Reopens: one clears the poisoning, one restores the handle after the
        # corrupt region's retry re-poisons it. If the corrupt region recovers on
        # the skip path (a victim reopened first), it reopens once more to retry on
        # a fresh handle before blanking, rather than trusting the shared handle —
        # so the exact count depends on recovery order.
        assert handle._generation in (2, 3)
