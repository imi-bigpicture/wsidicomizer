#    Copyright 2021, 2022, 2023 SECTRA AB
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

"""WsiInstance variant for `PixelImageData`-backed sources."""

from collections.abc import Sequence

import numpy as np
from wsidicom.geometry import Region, Size
from wsidicom.instance import WsiInstance
from wsidicom.instance.dataset import WsiDataset
from wsidicom.thread import ReadExecutor

from wsidicomizer.image_data import PixelImageData


class PixelWsiInstance(WsiInstance):
    """WsiInstance backed by a `PixelImageData`.

    Overrides `get_region` so reads go through the image data's ``read_region``
    method directly, instead of wsidicom's per-tile decode-and-stitch path.
    For pyramid levels this dispatches to a native region call (openslide /
    tiffslide / isyntax); for single-image associated images it crops the
    already-decoded image in memory.
    """

    _image_data: PixelImageData

    def __init__(
        self,
        datasets: WsiDataset | Sequence[WsiDataset],
        image_data: PixelImageData,
    ):
        super().__init__(datasets, image_data)

    def get_region(
        self,
        region: Region,
        z: float,
        path: str,
        output_size: Size | None = None,
        *,
        executor: ReadExecutor,
    ) -> np.ndarray:
        # Read the region straight from the image data, bypassing wsidicom's
        # per-tile decode-and-stitch path, then downsample if a smaller output
        # was requested.
        array = self._image_data.read_region(region, z, path)
        if output_size is None or output_size == region.size:
            return array
        return self._downsampler.downsample(array, output_size)
