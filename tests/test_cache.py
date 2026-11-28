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

import random
from collections.abc import Callable
from threading import Event, Thread

import numpy as np
import pytest

from wsidicomizer.cache import SharedDecodedFrameCache

TIMEOUT = 5.0
FRAME_BYTES = 48


class Call[ResultType]:
    """A call running in a daemon thread.

    A call that blocks then fails the test instead of hanging it.
    """

    def __init__(self, action: Callable[[], ResultType]) -> None:
        self._action = action
        self._results: list[ResultType] = []
        self._errors: list[Exception] = []
        self._started = Event()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        assert self._started.wait(TIMEOUT)

    def blocked(self) -> bool:
        """Return True if the call has not finished after running for a moment."""
        self._thread.join(0.1)
        return self._thread.is_alive()

    def result(self) -> ResultType:
        self._thread.join(TIMEOUT)
        assert not self._thread.is_alive(), "The call is blocked."
        if self._errors:
            raise self._errors[0]
        return self._results[0]

    def _run(self) -> None:
        self._started.set()
        try:
            self._results.append(self._action())
        except Exception as error:
            self._errors.append(error)


class FrameDecoder:
    """Decodes frames filled with their index, recording what is asked for.

    A held decoder does not return before it is released.
    """

    def __init__(self, held: bool = False, failure: Exception | None = None) -> None:
        self.decoded: list[int] = []
        self.decoding = Event()
        self._released = Event()
        if not held:
            self._released.set()
        self._failure = failure

    def release(self) -> None:
        self._released.set()

    def __call__(self, frame_index: int) -> np.ndarray:
        self.decoded.append(frame_index)
        self.decoding.set()
        assert self._released.wait(TIMEOUT)
        if self._failure is not None:
            raise self._failure
        return np.full((4, 4, 3), frame_index % 256, np.uint8)


@pytest.mark.unittest
class TestSharedDecodedFrameCache:
    def test_frame_asked_for_by_several_threads_is_decoded_once(self) -> None:
        # Arrange
        cache = SharedDecodedFrameCache(1024)
        decoder = FrameDecoder(held=True)
        first = Call(lambda: cache.get_tile_frame(1, 0, decoder))
        assert decoder.decoding.wait(TIMEOUT)

        # Act
        others = [Call(lambda: cache.get_tile_frame(1, 0, decoder)) for _ in range(7)]
        waited = [other.blocked() for other in others]
        decoder.release()
        frames = [call.result() for call in [first, *others]]

        # Assert
        assert all(waited)
        assert decoder.decoded == [0]
        assert all(frame is frames[0] for frame in frames)
        assert not frames[0].flags.writeable

    @pytest.mark.parametrize(["image_data_id", "frame_index"], [(1, 1), (2, 0)])
    def test_other_frame_is_decoded_while_a_frame_is_decoded(
        self, image_data_id: int, frame_index: int
    ) -> None:
        # Arrange
        cache = SharedDecodedFrameCache(1024)
        held = FrameDecoder(held=True)
        other = FrameDecoder()
        first = Call(lambda: cache.get_tile_frame(1, 0, held))
        assert held.decoding.wait(TIMEOUT)

        # Act
        Call(lambda: cache.get_tile_frame(image_data_id, frame_index, other)).result()
        held.release()

        # Assert
        assert other.decoded == [frame_index]
        first.result()

    def test_waiting_thread_decodes_the_frame_if_decoding_fails(self) -> None:
        # Arrange
        cache = SharedDecodedFrameCache(1024)
        failing = FrameDecoder(held=True, failure=OSError("corrupt"))
        working = FrameDecoder()
        first = Call(lambda: cache.get_tile_frame(1, 3, failing))
        assert failing.decoding.wait(TIMEOUT)

        # Act
        second = Call(lambda: cache.get_tile_frame(1, 3, working))
        waited = second.blocked()
        failing.release()

        # Assert
        assert waited
        with pytest.raises(OSError, match="corrupt"):
            first.result()
        assert second.result()[0, 0, 0] == 3
        assert working.decoded == [3]

    def test_thread_arriving_after_a_wait_still_shares_the_decode(self) -> None:
        # Arrange - a cache that can not keep a frame, so that each thread that
        # waited decodes it again
        cache = SharedDecodedFrameCache(1)
        first_decoder = FrameDecoder(held=True)
        second_decoder = FrameDecoder(held=True)
        third_decoder = FrameDecoder(held=True)
        fourth_decoder = FrameDecoder()
        first = Call(lambda: cache.get_tile_frame(1, 0, first_decoder))
        assert first_decoder.decoding.wait(TIMEOUT)
        second = Call(lambda: cache.get_tile_frame(1, 0, second_decoder))
        assert second.blocked()
        first_decoder.release()
        assert second_decoder.decoding.wait(TIMEOUT)
        third = Call(lambda: cache.get_tile_frame(1, 0, third_decoder))
        assert third_decoder.decoding.wait(TIMEOUT)
        second_decoder.release()
        second.result()

        # Act - the second thread must not have removed what the third holds
        fourth = Call(lambda: cache.get_tile_frame(1, 0, fourth_decoder))
        waited = fourth.blocked()
        decoded_while_waiting = list(fourth_decoder.decoded)
        third_decoder.release()

        # Assert
        assert waited
        assert decoded_while_waiting == []
        first.result()
        third.result()
        fourth.result()

    def test_cache_of_size_zero_decodes_every_time(self) -> None:
        # Arrange
        cache = SharedDecodedFrameCache(0)
        decoder = FrameDecoder()

        # Act
        for _ in range(2):
            Call(lambda: cache.get_tile_frame(1, 0, decoder)).result()

        # Assert
        assert decoder.decoded == [0, 0]

    def test_cleared_cache_decodes_again(self) -> None:
        # Arrange
        cache = SharedDecodedFrameCache(1024)
        decoder = FrameDecoder()
        Call(lambda: cache.get_tile_frame(1, 0, decoder)).result()
        cache.clear()

        # Act
        Call(lambda: cache.get_tile_frame(1, 0, decoder)).result()

        # Assert
        assert decoder.decoded == [0, 0]

    def test_concurrent_reads_with_failures_and_eviction(self) -> None:
        # Arrange - room for 5 of 20 frames
        cache = SharedDecodedFrameCache(5 * FRAME_BYTES)

        def read(seed: int) -> int:
            generator = random.Random(seed)

            def decode(frame_index: int) -> np.ndarray:
                if generator.random() < 0.05:
                    raise OSError("failed")
                return FrameDecoder()(frame_index)

            wrong = 0
            for _ in range(300):
                frame_index = generator.randrange(20)
                try:
                    frame = cache.get_tile_frame(1, frame_index, decode)
                except OSError:
                    continue
                wrong += int(frame[0, 0, 0] != frame_index)
            return wrong

        # Act
        calls = [Call(lambda seed=seed: read(seed)) for seed in range(16)]

        # Assert
        assert [call.result() for call in calls] == [0] * 16
