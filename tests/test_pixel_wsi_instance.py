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

import pytest
from decoy import Decoy
from PIL import Image as Pillow
from pydicom import Dataset
from pydicom.uid import JPEGBaseline8Bit
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.instance.dataset import WsiDataset
from wsidicom.metadata import ImageType

from wsidicomizer.image_data import PixelImageData
from wsidicomizer.pixel_wsi_instance import PixelWsiInstance


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
    """PixelWsiInstance routes get_region through PixelImageData.read_region."""

    def test_get_region_calls_read_region_with_exact_args(
        self,
        decoy: Decoy,
        instance: tuple[PixelWsiInstance, PixelImageData],
    ):
        # Arrange
        pixel_wsi_instance, image_data = instance
        region = Region(position=Point(100, 200), size=Size(400, 300))
        expected = Pillow.new("RGB", region.size.to_tuple())
        decoy.when(image_data.read_region(region, 0.0, "0")).then_return(expected)

        # Act
        result = pixel_wsi_instance.get_region(region, z=0.0, path="0")

        # Assert
        assert result is expected

    def test_get_region_downsamples_when_output_size_given(
        self,
        decoy: Decoy,
        instance: tuple[PixelWsiInstance, PixelImageData],
    ):
        # Arrange
        pixel_wsi_instance, image_data = instance
        region = Region(position=Point(0, 0), size=Size(400, 300))
        output_size = Size(200, 150)
        image = Pillow.new("RGB", region.size.to_tuple())
        decoy.when(image_data.read_region(region, 0.0, "0")).then_return(image)
        expected = image.resize(
            output_size.to_tuple(), resample=Pillow.Resampling.BILINEAR
        )

        # Act
        result = pixel_wsi_instance.get_region(
            region, z=0.0, path="0", output_size=output_size
        )

        # Assert — result downsampled to output_size (native read returned region size)
        assert result == expected

    def test_get_region_skips_downsample_when_output_matches_region(
        self,
        decoy: Decoy,
        instance: tuple[PixelWsiInstance, PixelImageData],
    ):
        # Arrange
        pixel_wsi_instance, image_data = instance
        region = Region(position=Point(0, 0), size=Size(400, 300))
        native = Pillow.new("RGB", region.size.to_tuple())
        decoy.when(image_data.read_region(region, 0.0, "0")).then_return(native)

        # Act
        result = pixel_wsi_instance.get_region(
            region, z=0.0, path="0", output_size=region.size
        )

        # Assert — returns the native image unmodified (`is` identity)
        assert result is native
