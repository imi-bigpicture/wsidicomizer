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

"""Unit tests for OpenTileImageData."""

import pytest
from decoy import Decoy
from opentile.geometry import Size
from opentile.jpeg2000 import Jpeg2000Info
from opentile.tiff_image import AssociatedTiffImage
from pydicom.uid import JPEG2000, UID, JPEG2000Lossless
from tifffile import PHOTOMETRIC
from wsidicom.codec import Encoder

from wsidicomizer.sources.opentile.opentile_image_data import (
    OpenTileAssociatedImageData,
)


@pytest.mark.unittest
class TestOpenTileImageData:
    @pytest.mark.parametrize(
        [
            "reversible",
            "uses_mct",
            "subsampling",
            "expected_transfer_syntax",
            "expected_photometric_interpretation",
        ],
        [
            # Colour transform inside the codestream: YBR_ICT/YBR_RCT.
            (False, True, (1, 1), JPEG2000, "YBR_ICT"),
            (True, True, (1, 1), JPEG2000Lossless, "YBR_RCT"),
            # Colour transform outside the codestream, no subsampling: YBR_FULL.
            (False, False, (1, 1), JPEG2000, "YBR_FULL"),
            (True, False, (1, 1), JPEG2000Lossless, "YBR_FULL"),
            (False, False, None, JPEG2000, "YBR_FULL"),
            # Colour transform outside the codestream, subsampled chroma:
            # YBR_FULL_422 (e.g. Aperio 33003), which also covers 4:2:0.
            (False, False, (2, 1), JPEG2000, "YBR_FULL_422"),
            (False, False, (2, 2), JPEG2000, "YBR_FULL_422"),
            (True, False, (2, 1), JPEG2000Lossless, "YBR_FULL_422"),
        ],
    )
    def test_photometric_interpretation_of_ycbcr_jpeg2000(
        self,
        decoy: Decoy,
        reversible: bool,
        uses_mct: bool,
        subsampling: tuple[int, int] | None,
        expected_transfer_syntax: UID,
        expected_photometric_interpretation: str,
    ):
        # Arrange
        tiff_image = decoy.mock(cls=AssociatedTiffImage)
        decoy.when(tiff_image.photometric_interpretation).then_return(PHOTOMETRIC.YCBCR)
        decoy.when(tiff_image.encoded_info).then_return(
            Jpeg2000Info(
                reversible=reversible,
                uses_mct=uses_mct,
                components=3,
                subsampling=subsampling,
                bit_depth=8,
                extended=False,
            )
        )
        decoy.when(tiff_image.image_size).then_return(Size(512, 512))
        decoy.when(tiff_image.tile_size).then_return(Size(256, 256))
        decoy.when(tiff_image.tiled_size).then_return(Size(2, 2))
        decoy.when(tiff_image.pixel_spacing).then_return(None)
        encoder = decoy.mock(cls=Encoder)

        # Act
        image_data = OpenTileAssociatedImageData(tiff_image, encoder)

        # Assert
        assert image_data.transfer_syntax == expected_transfer_syntax
        assert (
            image_data.photometric_interpretation == expected_photometric_interpretation
        )
