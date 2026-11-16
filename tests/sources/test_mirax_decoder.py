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

"""Tests for choosing the decoder of a stored MIRAX blob."""

import pytest

from wsidicomizer.sources.mirax.reader.decoder import (
    MiraxBmpDecoder,
    MiraxDecoder,
    MiraxDecoderFactory,
    MiraxJpeg2000Decoder,
    MiraxJpegDecoder,
    MiraxJpegXrDecoder,
    MiraxPngDecoder,
    MiraxSniffingDecoder,
)


@pytest.mark.unittest
class TestMiraxDecoderFactory:
    @pytest.mark.parametrize(
        ["image_format", "expected"],
        [
            ("JPEG", MiraxJpegDecoder),
            ("JPEG_RGB", MiraxJpegDecoder),
            ("BMP24", MiraxBmpDecoder),
            ("PNG", MiraxPngDecoder),
            ("JPEGXR", MiraxJpegXrDecoder),
            ("JPEG2000", MiraxJpeg2000Decoder),
            ("UNKNOWN", MiraxSniffingDecoder),
        ],
    )
    def test_for_image_format(self, image_format: str, expected: type[MiraxDecoder]):
        # Arrange

        # Act
        decoder = MiraxDecoderFactory.for_image_format(image_format)

        # Assert
        assert isinstance(decoder, expected)

    @pytest.mark.parametrize(
        ["blob", "expected"],
        [
            (b"\xff\xd8\xff\xe0", MiraxJpegDecoder),
            (b"BM\x00\x00", MiraxBmpDecoder),
            (b"\x89PNG\r\n", MiraxPngDecoder),
            (b"\x49\x49\xbc\x01\x00", MiraxJpegXrDecoder),
            (b"\x00\x00\x00\x0cjP  ", MiraxJpeg2000Decoder),
            (b"GIF89a", MiraxSniffingDecoder),
        ],
    )
    def test_for_blob(self, blob: bytes, expected: type[MiraxDecoder]):
        # Arrange

        # Act
        decoder = MiraxDecoderFactory.for_blob(blob)

        # Assert
        assert isinstance(decoder, expected)
