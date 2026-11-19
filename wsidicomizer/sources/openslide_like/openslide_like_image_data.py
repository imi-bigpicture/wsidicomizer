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

from collections.abc import Sequence

from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Size
from wsidicom.metadata import Image as ImageMetadata

from wsidicomizer.image_data import PixelLevelImageData


class OpenSlideLikeLevelImageData(PixelLevelImageData):
    """A level of an OpenSlide-like pyramid, optionally limited to the slide's
    bounds."""

    def __init__(
        self,
        blank_color: int | tuple[int, int, int] | None,
        offset: Point | None,
        size: Size | None,
        level_dimensions: Sequence[tuple[int, int]],
        level_downsamples: Sequence[float],
        image_metadata: ImageMetadata,
        level_index: int,
        tile_size: int | None,
        encoder: Encoder,
    ):
        """Create a level of an OpenSlide-like pyramid.

        Parameters
        ----------
        blank_color: int | tuple[int, int, int] | None
            Background color for empty regions, or None for the encoder's default.
        offset: Point | None
            Base-level position of the slide's bounds, or None if unbounded.
        size: Size | None
            Base-level size of the slide's bounds, or None if unbounded.
        level_dimensions: Sequence[tuple[int, int]]
            Dimensions of every level.
        level_downsamples: Sequence[float]
            Downsamples of every level.
        image_metadata: ImageMetadata
            Image metadata of the base level.
        level_index: int
            Index of this level.
        tile_size: int | None
            Output tile size. If None, the default tile size is used.
        encoder: Encoder
            Encoder that encodes every tile.
        """
        downsample = level_downsamples[level_index]
        if size is not None:
            image_size = size // int(round(downsample))
            base_size = size
        else:
            image_size = Size.from_tuple(level_dimensions[level_index])
            base_size = Size.from_tuple(level_dimensions[0])
        super().__init__(
            image_size,
            image_metadata,
            tile_size,
            blank_color,
            encoder,
            downsample=downsample,
            base_size=base_size,
        )
        self._level_index = level_index
        self._downsample = downsample
        self._offset = offset or Point(0, 0)
