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

"""Caches of the sources."""

from collections.abc import Callable
from threading import Lock

import numpy as np
from wsidicom.cache import DecodedFrameCache


class SharedDecodedFrameCache(DecodedFrameCache):
    """Decoded frame cache that decodes a frame once for threads asking at once.

    Sources that compose tiles from larger or overlapping stored frames have
    neighbouring tiles, read by different threads, that need the same frame. A lock
    per frame makes the later threads wait for the first to decode and cache it. If
    that fails, or the frame is not kept by the cache, they decode it themselves.

    Only frames asked for one at a time, with `get_tile_frame()`, are shared. The
    function decoding a frame must not ask the cache for that frame.
    """

    def __init__(self, size: int) -> None:
        """Create a cache.

        Parameters
        ----------
        size: int
            The most bytes of decoded frames to keep.
        """
        super().__init__(size)
        self._decode_locks: dict[tuple[int, int], Lock] = {}

    def get_tile_frame(
        self,
        image_data_id: int,
        frame_index: int,
        frame_getter: Callable[[int], np.ndarray],
    ) -> np.ndarray:
        """Return a frame from the cache, decoding it if it is missing.

        Parameters
        ----------
        image_data_id: int
            Id of what the frame belongs to.
        frame_index: int
            Index of the frame.
        frame_getter: Callable[[int], np.ndarray]
            Decodes the frame of an index.

        Returns
        -------
        np.ndarray
            The frame, read-only if the cache keeps frames.
        """
        if self._lru_cache.maxsize < 1:
            return frame_getter(frame_index)
        key = (image_data_id, frame_index)
        # A cached frame is returned without taking a lock.
        frame = self._lru_cache.get(key)
        if frame is not None:
            return frame
        lock = self._decode_locks.setdefault(key, Lock())
        with lock:
            try:
                return super().get_tile_frame(image_data_id, frame_index, frame_getter)
            finally:
                # A thread that waited for the lock must not remove a lock created
                # for the frame after this one was removed.
                if self._decode_locks.get(key) is lock:
                    del self._decode_locks[key]
