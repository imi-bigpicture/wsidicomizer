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

class Settings:
    """Class containing settings. Settings are to be accessed through the
    global variable settings."""
    def __init__(self) -> None:
        self._czi_block_cache_size = 8

    @property
    def czi_block_cache_size(self) -> int:
        """Size of block cache to use for czi files."""
        return self._czi_block_cache_size

    @czi_block_cache_size.setter
    def czi_block_cache_size(self, value: int) -> None:
        self._czi_block_cache_size = value


settings = Settings()
"""Global settings variable."""