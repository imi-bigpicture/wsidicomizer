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

"""Green-field MIRAX (.mrxs) reader.

Exposes a level-local pyramid/tile read API returning Pillow images. Format
reverse-engineered from https://openslide.org/formats/mirax/ and verified
against the openslide test slides; no openslide code was used.
"""

from wsidicomizer.sources.mirax.reader.errors import MrxsError
from wsidicomizer.sources.mirax.reader.mirax_reader import (
    MiraxAssociatedImageType,
    MiraxReader,
)

__all__ = ["MrxsError", "MiraxAssociatedImageType", "MiraxReader"]
