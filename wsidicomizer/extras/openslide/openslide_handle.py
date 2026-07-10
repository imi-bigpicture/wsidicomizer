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

"""Shared OpenSlide handle with reopen-on-poison recovery."""

import ctypes
from collections.abc import Mapping
from functools import cached_property
from pathlib import Path
from threading import Condition

import numpy as np
from PIL.Image import Image
from PIL.ImageCms import ImageCmsProfile

from wsidicomizer.config import settings
from wsidicomizer.extras.openslide.openslide import (
    OpenSlide,
    OpenSlideError,
    _read_region,
)


class OpenSlideHandle:
    """Shared OpenSlide handle with reopen-on-poison recovery (issue #146).

    A failed ``read_region`` can leave the handle poisoned. Once that happens, every
    subsequent read on the same handle fails until the handle is reopened. The handle
    is shared by all reading threads, so without recovery a single poisoning would
    fail every remaining read of the slide.

    Use :meth:`read` for reads. On the happy path it only registers the read as
    in-flight. When a read fails, recovery runs serially. The recovering thread
    blocks all new reads and drains the in-flight ones to zero. It then reopens the
    handle and retries the failed read alone. If the read then fails on a fresh
    handle, it is genuinely unreadable. Such regions are rendered blank. The
    conversion aborts once more than ``settings.openslide_unreadable_region_limit``
    regions have failed.
    """

    def __init__(self, filepath: Path) -> None:
        self._filepath = filepath
        self._slide = OpenSlide(filepath)
        self._osr = self._slide._osr
        # Bumped on every reopen. A read snapshots it before reading; recovery
        # compares that snapshot against the current value to tell whether the handle
        # was already reopened since the read failed (so it does not reopen again).
        self._generation = 0
        self._condition = Condition()
        self._readers = 0
        self._recovering = False
        self._unreadable_regions = 0

    @cached_property
    def properties(self) -> Mapping[str, str]:
        """OpenSlide properties of the slide."""
        return dict(self._slide.properties)

    @cached_property
    def level_dimensions(self) -> tuple[tuple[int, int], ...]:
        """The ``(width, height)`` of each level."""
        return self._slide.level_dimensions

    @cached_property
    def level_downsamples(self) -> tuple[float, ...]:
        """The downsample factor of each level."""
        return self._slide.level_downsamples

    @cached_property
    def associated_images(self) -> Mapping[str, Image]:
        """Associated images (label, macro, ...). OpenSlide decodes each on access, so
        this reads them all into independent images, decoupled from the handle."""
        return dict(self._slide.associated_images)

    @cached_property
    def color_profile(self) -> ImageCmsProfile | None:
        """ICC color profile of the slide, or None."""
        return self._slide.color_profile

    def read(
        self, x: int, y: int, level: int, width: int, height: int
    ) -> np.ndarray | None:
        """Read a region from the shared handle, recovering from a poisoned handle.

        Parameters
        ----------
        x: int
            X of the region's top-left in the level-0 reference frame.
        y: int
            Y of the region's top-left in the level-0 reference frame.
        level: int
            Level to read from.
        width: int
            Width of the region to read.
        height: int
            Height of the region to read.

        Returns
        -------
        np.ndarray | None
            The region as an ARGB array of shape ``(height, width, 4)``, or None if
            it is unreadable and should be rendered blank.
        """
        CHANNELS = 4
        region_data = np.empty((height, width, CHANNELS), dtype=ctypes.c_uint8)
        generation = self._enter_read()
        try:
            self._read(region_data, x, y, level, width, height)
            return region_data
        except OpenSlideError:
            pass
        finally:
            self._exit_read()
        if self._recover(generation, region_data, x, y, level, width, height):
            return region_data
        return None

    def _read(
        self,
        region_data: np.ndarray,
        x: int,
        y: int,
        level: int,
        width: int,
        height: int,
    ) -> None:
        """Read a region from the current handle into ``region_data``.

        Parameters
        ----------
        region_data: np.ndarray
            Destination ARGB buffer of shape ``(height, width, 4)`` to read into.
        x: int
            X of the region's top-left in the level-0 reference frame.
        y: int
            Y of the region's top-left in the level-0 reference frame.
        level: int
            Level to read from.
        width: int
            Width of the region to read.
        height: int
            Height of the region to read.

        Raises
        ------
        OpenSlideError
            If the read fails.
        """
        _read_region(
            self._osr,
            region_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
            x,
            y,
            level,
            width,
            height,
        )

    def _enter_read(self) -> int:
        """Register an in-flight read, waiting if a recovery is in progress.
        Returns the generation observed, to detect a reopen by the time recovery
        starts."""
        with self._condition:
            while self._recovering:
                self._condition.wait()
            self._readers += 1
            return self._generation

    def _exit_read(self) -> None:
        """Deregister an in-flight read, waking any waiting recovery once the last
        reader has left."""
        with self._condition:
            self._readers -= 1
            if self._readers == 0:
                self._condition.notify_all()

    def _reopen(self) -> None:
        """Close the poisoned handle and open a fresh one, bumping the generation.

        Only ever called from :meth:`_recover`, after in-flight reads are drained to
        zero and new reads are blocked, so no thread can still be using the old
        handle and closing it immediately is safe."""
        assert self._recovering and self._readers == 0, (
            "_reopen requires the recovery lock held with all readers drained"
        )
        self._slide.close()
        self._slide = OpenSlide(self._filepath)
        self._osr = self._slide._osr
        self._generation += 1

    def _recover(
        self,
        read_generation: int,
        region_data: np.ndarray,
        x: int,
        y: int,
        level: int,
        width: int,
        height: int,
    ) -> bool:
        """Recover from a failed read by reopening and retrying in isolation. Blocks
        new reads, waits for any in-progress recovery and for in-flight reads to drain
        to zero, then reopens the handle (unless already reopened for this poisoning)
        and retries the read alone, filling ``region_data`` in place.

        Parameters
        ----------
        read_generation: int
            The generation the failed read ran at, used to tell whether the handle
            has already been reopened for this poisoning.
        region_data: np.ndarray
            Destination ARGB buffer of shape ``(height, width, 4)`` to read into.
        x: int
            X of the region's top-left in the level-0 reference frame.
        y: int
            Y of the region's top-left in the level-0 reference frame.
        level: int
            Level to read from.
        width: int
            Width of the region to read.
        height: int
            Height of the region to read.

        Returns
        -------
        bool
            True on success, or False if the region is still unreadable on a fresh
            handle (and should be rendered blank).
        """
        with self._condition:
            while self._recovering:  # one recovery at a time
                self._condition.wait()
            self._recovering = True  # block new reads (see _enter_read)
            try:
                while self._readers > 0:  # drain in-flight reads
                    self._condition.wait()
                if self._generation == read_generation:
                    # First to observe this poisoning: reopen, so a failed read here
                    # is on a guaranteed-fresh handle and is therefore definitive.
                    self._reopen()
                    try:
                        self._read(region_data, x, y, level, width, height)
                        return True
                    except OpenSlideError as error:
                        return self._mark_unreadable(error)
                # A prior victim of the same poisoning already reopened, but the
                # handle may have been re-poisoned since by another thread's bad read
                # (whose sticky error persists after that read has drained). Try the
                # current handle; only if that fails do we reopen for a definitive,
                # isolated retry -- so a good region is never blanked just because
                # another region poisoned the shared handle.
                try:
                    self._read(region_data, x, y, level, width, height)
                    return True
                except OpenSlideError:
                    self._reopen()
                try:
                    self._read(region_data, x, y, level, width, height)
                    return True
                except OpenSlideError as error:
                    return self._mark_unreadable(error)
            finally:
                self._recovering = False
                self._condition.notify_all()

    def _mark_unreadable(self, error: OpenSlideError) -> bool:
        """Record a region that failed to read on a freshly reopened handle. The
        failed read left the handle poisoned, so reopen to leave a clean one for the
        next waiter, count the region against the limit, and return False so it is
        rendered blank. Raises once the limit is exceeded.

        Only ever called after a read that failed on a handle reopened within this
        recovery's lock hold, so the failure is genuinely the region's, not a
        collateral poisoning from another thread."""
        self._reopen()
        self._unreadable_regions += 1
        limit = settings.openslide_unreadable_region_limit
        if self._unreadable_regions > limit:
            raise RuntimeError(
                f"Aborting: {self._unreadable_regions} regions of {self._filepath} "
                f"could not be read even after reopening the OpenSlide handle, "
                f"exceeding the accepted limit of {limit} "
                f"(settings.openslide_unreadable_region_limit). The file may be "
                f"corrupt or otherwise unreadable."
            ) from error
        return False

    def close(self) -> None:
        self._slide.close()
