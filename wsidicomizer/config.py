#    Copyright 2022 SECTRA AB
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

"""Module containing settings for WsiDicomizer.

``Settings`` extends the wsidicom ``Settings`` (so every wsidicom setting, such
as ``pyramid_resampling_filter``, is a first-class field here) and adds
wsidicomizer's own settings and per-source settings (e.g. ``opentile``).
"""

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from opentile.config import Settings as OpenTileSettings
from opentile.config import set_default_settings as set_opentile_default_settings
from opentile.config import use_settings as use_opentile_settings
from wsidicom.config import Settings as DicomSettings
from wsidicom.config import set_default_settings as set_dicom_default_settings
from wsidicom.config import use_settings as use_dicom_settings


@dataclass(frozen=True)
class Settings(DicomSettings):
    """Immutable settings for WsiDicomizer.

    Inherits all wsidicom settings and adds wsidicomizer's own. To change the
    process-wide default, use ``set_default_settings(Settings(...))``. To apply
    settings to a block of code, use ``use_settings``.
    """

    default_tile_size: int = 512
    """Default tile size to use."""
    czi_block_cache_size: int = 8
    """Size of block cache to use for czi files."""
    insert_icc_profile_if_missing: bool = True
    """Whether to insert a default ICC profile in the DICOM file if no profile
    is present in the source file or provided metadata."""
    opentile: OpenTileSettings = field(default_factory=OpenTileSettings)
    """Settings for the opentile source (e.g. used when reading NDPI files)."""


_default_settings = Settings()
_active_settings: contextvars.ContextVar[Settings | None] = contextvars.ContextVar(
    "wsidicomizer_active_settings", default=None
)


def get_settings() -> Settings:
    """The settings in effect: those active in the current context (see
    ``use_settings``), or the process-wide default when none is active."""
    return _active_settings.get() or _default_settings


def set_default_settings(new_settings: Settings) -> None:
    """Replace the process-wide default settings.

    The change is propagated to the wsidicom and opentile default settings the
    ``Settings`` carries, so all three layers stay in agreement.
    """
    global _default_settings
    _default_settings = new_settings
    set_dicom_default_settings(new_settings)
    set_opentile_default_settings(new_settings.opentile)


@contextmanager
def use_settings(active: Settings | None = None) -> Iterator[Settings]:
    """Activate wsidicomizer settings for the current context and yield the
    settings in effect.

    With an ``active`` ``Settings`` it activates it here, together with the
    wsidicom and opentile layers it carries, so all three agree, and resets on
    exit. With no argument it activates nothing (each layer keeps its own
    default) and just yields the settings currently in effect.
    """
    if active is None:
        yield get_settings()
        return
    with use_dicom_settings(active), use_opentile_settings(active.opentile):
        token = _active_settings.set(active)
        try:
            yield active
        finally:
            _active_settings.reset(token)
