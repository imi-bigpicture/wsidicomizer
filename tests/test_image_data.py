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

"""Tests for the blank-frame handling shared by `BaseDicomizerImageData`.

Exercised through `TiffSlideLevelImageData`, the simplest of the pixel sources
to construct; the openslide and isyntax sources return blank regions through
the same base-class helper.
"""

import numpy as np
import pytest
from decoy import Decoy
from tiffslide import TiffSlide
from wsidicom.codec import Encoder
from wsidicom.codec.settings import JpegSettings
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata

from wsidicomizer.sources.tiffslide.tiffslide_image_data import TiffSlideLevelImageData

BLANK_COLOR = (255, 255, 255)


def frame(size: Size, color: int) -> np.ndarray:
    """A decoded frame as tiffslide produces it: `(rows, columns, samples)`.

    Returned as a bare `np.ndarray`; tiffslide types the `as_array=True`
    overload of `read_region` as `NDArray[np.int_]`, but hands back the uint8
    image data this builds.
    """
    return np.full((size.height, size.width, 3), color, np.uint8)


@pytest.fixture
def encoder() -> Encoder:
    return Encoder.create_for_settings(JpegSettings())


@pytest.fixture
def image_data(
    decoy: Decoy, encoder: Encoder
) -> tuple[TiffSlideLevelImageData, TiffSlide]:
    tiff_slide = decoy.mock(cls=TiffSlide)
    decoy.when(tiff_slide.level_dimensions).then_return(((1024, 1024),))
    decoy.when(tiff_slide.level_downsamples).then_return((1.0,))
    decoy.when(tiff_slide.properties).then_return({"tiffslide.series-axes": "YXS"})
    return (
        TiffSlideLevelImageData(
            tiff_slide,
            BLANK_COLOR,
            None,
            None,
            ImageMetadata(pixel_spacing=SizeMm(0.001, 0.001)),
            0,
            512,
            encoder,
        ),
        tiff_slide,
    )


@pytest.mark.unittest
class TestBlankRegion:
    """A region that is entirely background is returned with the same shape as
    one read from the source: `(rows, columns, samples)`, i.e. height first."""

    @pytest.mark.parametrize("size", [Size(1024, 256), Size(256, 1024), Size(512, 512)])
    def test_blank_region_has_rows_columns_shape(
        self,
        decoy: Decoy,
        image_data: tuple[TiffSlideLevelImageData, TiffSlide],
        size: Size,
    ):
        # Arrange
        level_image_data, tiff_slide = image_data
        region = Region(position=Point(0, 0), size=size)
        background = frame(size, 255)
        decoy.when(
            tiff_slide.read_region((0, 0), 0, size.to_tuple(), as_array=True)
        ).then_return(background)

        # Act
        result = level_image_data.read_region(region, 0.0, "1")

        # Assert
        assert result.shape == (size.height, size.width, 3)

    def test_blank_and_read_region_agree_on_shape(
        self,
        decoy: Decoy,
        image_data: tuple[TiffSlideLevelImageData, TiffSlide],
    ):
        # Arrange
        level_image_data, tiff_slide = image_data
        size = Size(1024, 256)
        blank_region = Region(position=Point(0, 0), size=size)
        tissue_region = Region(position=Point(0, 256), size=size)
        background = frame(size, 255)
        tissue = frame(size, 0)
        decoy.when(
            tiff_slide.read_region((0, 0), 0, size.to_tuple(), as_array=True)
        ).then_return(background)
        decoy.when(
            tiff_slide.read_region((0, 256), 0, size.to_tuple(), as_array=True)
        ).then_return(tissue)

        # Act
        blank_result = level_image_data.read_region(blank_region, 0.0, "1")
        tissue_result = level_image_data.read_region(tissue_region, 0.0, "1")

        # Assert
        assert blank_result.shape == tissue_result.shape
