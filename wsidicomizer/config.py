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

"""Module containing settings for WsiDicomizer."""


class Settings:
    """Class containing settings. Settings are to be accessed through the
    global variable settings."""

    def __init__(self) -> None:
        self._default_tile_size = 512
        self._czi_block_cache_size = 8
        self._insert_icc_profile_if_missing = True
        self._openslide_unreadable_region_limit = 16

    @property
    def default_tile_size(self) -> int:
        """Default tile size to use."""
        return self._default_tile_size

    @default_tile_size.setter
    def default_tile_size(self, value: int) -> None:
        self._default_tile_size = value

    @property
    def czi_block_cache_size(self) -> int:
        """Size of block cache to use for czi files."""
        return self._czi_block_cache_size

    @czi_block_cache_size.setter
    def czi_block_cache_size(self, value: int) -> None:
        self._czi_block_cache_size = value

    @property
    def insert_icc_profile_if_missing(self) -> bool:
        """Whether to insert a default ICC profile in the DICOM file if no profile
        is present in the source file or provided metadata."""
        return self._insert_icc_profile_if_missing

    @insert_icc_profile_if_missing.setter
    def insert_icc_profile_if_missing(self, value: bool) -> None:
        self._insert_icc_profile_if_missing = value

    @property
    def openslide_unreadable_region_limit(self) -> int:
        """Maximum number of regions that may fail to read (and be rendered blank)
        before an OpenSlide conversion is aborted. A failed read poisons the shared
        OpenSlide handle for all threads; the handle is reopened to recover, but
        regions that still fail on a fresh handle are counted against this limit.
        Set to 0 to abort on the first unreadable region."""
        return self._openslide_unreadable_region_limit

    @openslide_unreadable_region_limit.setter
    def openslide_unreadable_region_limit(self, value: int) -> None:
        self._openslide_unreadable_region_limit = value


settings = Settings()
"""Global settings variable."""
