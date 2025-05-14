#    Copyright 2025 SECTRA AB
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

"""Module containing partial implemented source for reading files with openslide like
interface."""

from wsidicomizer.sources.openslide_like.openslide_like_image_data import (
    OpenSlideLikeAssociatedImageData,
    OpenSlideLikeLevelImageData,
    OpenSlideLikeThumbnailImageData,
)
from wsidicomizer.sources.openslide_like.openslide_like_metadata import (
    OpenSlideLikeMetadata,
    OpenSlideLikeProperties,
)
from wsidicomizer.sources.openslide_like.openslide_like_source import (
    OpenSlideLikeSource,
)

__all__ = [
    "OpenSlideLikeSource",
    "OpenSlideLikeMetadata",
    "OpenSlideLikeProperties",
    "OpenSlideLikeLevelImageData",
    "OpenSlideLikeAssociatedImageData",
    "OpenSlideLikeThumbnailImageData",
]
