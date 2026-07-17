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

"""Tests for PixelWsiInstance / PixelImageData wiring."""

import numpy as np
import pytest
from decoy import Decoy
from pydicom import Dataset
from pydicom.uid import JPEGBaseline8Bit
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.instance.dataset import WsiDataset
from wsidicom.metadata import ImageType
from wsidicom.thread import ReadExecutor

from wsidicomizer.image_data import PixelImageData
from wsidicomizer.pixel_wsi_instance import PixelWsiInstance


@pytest.fixture
def read_executor() -> ReadExecutor:
    return ReadExecutor(None, None)


@pytest.fixture
def size() -> Size:
    return Size(1024, 1024)


@pytest.fixture
def tile_size() -> Size:
    return Size(512, 512)


@pytest.fixture
def instance(
    decoy: Decoy, size: Size, tile_size: Size
) -> tuple[PixelWsiInstance, PixelImageData]:
    image_data = decoy.mock(cls=PixelImageData)
    decoy.when(image_data.transfer_syntax).then_return(JPEGBaseline8Bit)
    decoy.when(image_data.image_size).then_return(size)
    decoy.when(image_data.tile_size).then_return(tile_size)
    decoy.when(image_data.tiled_size).then_return(size.ceil_div(tile_size))
    decoy.when(image_data.pixel_spacing).then_return(SizeMm(0.001, 0.001))
    decoy.when(image_data.imaged_size).then_return(SizeMm(0.001, 0.001) * size)
    decoy.when(image_data.samples_per_pixel).then_return(3)
    decoy.when(image_data.photometric_interpretation).then_return("YBR_FULL_422")
    decoy.when(image_data.bits).then_return(8)
    decoy.when(image_data.image_coordinate_system).then_return(None)
    decoy.when(image_data.thread_safe).then_return(True)
    decoy.when(image_data.lossy_compression).then_return(None)
    decoy.when(image_data.transcoder).then_return(None)
    decoy.when(image_data.focal_planes).then_return([0.0])
    decoy.when(image_data.optical_paths).then_return(["0"])
    decoy.when(image_data.default_z).then_return(0.0)
    decoy.when(image_data.default_path).then_return("0")

    base = Dataset()
    base.StudyInstanceUID = "1.2.3"
    base.SeriesInstanceUID = "1.2.4"
    base.SOPInstanceUID = "1.2.5"
    base.FrameOfReferenceUID = "1.2.6"
    instance_dataset = WsiDataset.create_instance_dataset(
        base, ImageType.VOLUME, image_data, pyramid_index=0
    )
    return PixelWsiInstance(instance_dataset, image_data), image_data


@pytest.mark.unittest
class TestPixelWsiInstance:
    """PixelWsiInstance reads via PixelImageData.read_region, returning the
    numpy array directly and downsampling it in numpy when asked for a smaller
    output."""

    def test_get_region_returns_read_region_array(
        self,
        decoy: Decoy,
        instance: tuple[PixelWsiInstance, PixelImageData],
        read_executor: ReadExecutor,
    ):
        # Arrange
        pixel_wsi_instance, image_data = instance
        region = Region(position=Point(100, 200), size=Size(400, 300))
        array = np.zeros((300, 400, 3), np.uint8)
        decoy.when(image_data.read_region(region, 0.0, "0")).then_return(array)

        # Act
        result = pixel_wsi_instance.get_region(
            region, z=0.0, path="0", executor=read_executor
        )

        # Assert — the native array is returned unmodified (`is` identity)
        assert result is array

    def test_get_region_downsamples_when_output_size_given(
        self,
        decoy: Decoy,
        instance: tuple[PixelWsiInstance, PixelImageData],
        read_executor: ReadExecutor,
    ):
        # Arrange
        pixel_wsi_instance, image_data = instance
        region = Region(position=Point(0, 0), size=Size(400, 300))
        output_size = Size(200, 150)
        array = np.zeros((300, 400, 3), np.uint8)
        decoy.when(image_data.read_region(region, 0.0, "0")).then_return(array)

        # Act
        result = pixel_wsi_instance.get_region(
            region, z=0.0, path="0", output_size=output_size, executor=read_executor
        )

        # Assert — array downsampled to output_size, still numpy (rows, cols, 3)
        assert isinstance(result, np.ndarray)
        assert result.shape == (output_size.height, output_size.width, 3)

    def test_get_region_skips_downsample_when_output_matches_region(
        self,
        decoy: Decoy,
        instance: tuple[PixelWsiInstance, PixelImageData],
        read_executor: ReadExecutor,
    ):
        # Arrange
        pixel_wsi_instance, image_data = instance
        region = Region(position=Point(0, 0), size=Size(400, 300))
        array = np.zeros((300, 400, 3), np.uint8)
        decoy.when(image_data.read_region(region, 0.0, "0")).then_return(array)

        # Act
        result = pixel_wsi_instance.get_region(
            region, z=0.0, path="0", output_size=region.size, executor=read_executor
        )

        # Assert — returns the native array unmodified (`is` identity)
        assert result is array
