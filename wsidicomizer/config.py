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
        self._fallback_to_blank_tile_on_error = False

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
    def fallback_to_blank_tile_on_error(self) -> bool:
        """Whether to fallback to a blank tile if an error occurs when reading a tile
        from the source file."""
        return self._fallback_to_blank_tile_on_error

    @fallback_to_blank_tile_on_error.setter
    def fallback_to_blank_tile_on_error(self, value: bool) -> None:
        self._fallback_to_blank_tile_on_error = value


settings = Settings()
"""Global settings variable."""
