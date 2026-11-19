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

"""Decoders for the blobs stored in a MIRAX slide's data files.

Tiles are encoded as the slide's IMAGE_FORMAT states; associated images carry
their own format, recognized by magic bytes. A format-specific imagecodecs
decoder skips imagecodecs.imread's format sniffing (and its EXR-probe noise).
8-bit formats decode to uint8 (H, W, 3); 16-bit ones to uint16 (H, W, 3).
"""

from abc import ABCMeta, abstractmethod

import imagecodecs
import numpy as np


class MiraxDecoder(metaclass=ABCMeta):
    """Decodes one encoding of stored MIRAX blobs to a numpy array."""

    image_formats: tuple[str, ...] = ()
    """The IMAGE_FORMAT values of tiles in this encoding."""
    magic: bytes | None = None
    """The bytes a blob in this encoding starts with."""

    @abstractmethod
    def decode(self, blob: bytes) -> np.ndarray:
        """Decode a blob.

        Parameters
        ----------
        blob: bytes
            The stored bytes.

        Returns
        -------
        np.ndarray
            The decoded pixels.
        """
        raise NotImplementedError()


class MiraxJpegDecoder(MiraxDecoder):
    image_formats = ("JPEG", "JPEG_RGB")
    magic = b"\xff\xd8\xff"

    def decode(self, blob: bytes) -> np.ndarray:
        return imagecodecs.jpeg_decode(blob)


class MiraxBmpDecoder(MiraxDecoder):
    image_formats = ("BMP24",)
    magic = b"BM"

    def decode(self, blob: bytes) -> np.ndarray:
        return imagecodecs.bmp_decode(blob)


class MiraxPngDecoder(MiraxDecoder):
    image_formats = ("PNG",)
    magic = b"\x89PNG"

    def decode(self, blob: bytes) -> np.ndarray:
        return imagecodecs.png_decode(blob)


class MiraxJpegXrDecoder(MiraxDecoder):
    image_formats = ("JPEGXR",)
    magic = b"\x49\x49\xbc\x01"

    def decode(self, blob: bytes) -> np.ndarray:
        return imagecodecs.jpegxr_decode(blob)


class MiraxJpeg2000Decoder(MiraxDecoder):
    image_formats = ("JPEG2000",)
    magic = b"\x00\x00\x00\x0c"

    def decode(self, blob: bytes) -> np.ndarray:
        return imagecodecs.jpeg2k_decode(blob)


class MiraxSniffingDecoder(MiraxDecoder):
    """Decodes a blob of a format not listed, recognized by imagecodecs.imread."""

    def decode(self, blob: bytes) -> np.ndarray:
        return imagecodecs.imread(blob)


class MiraxDecoderFactory:
    """Chooses the decoder for stored MIRAX blobs."""

    _DECODERS: tuple[MiraxDecoder, ...] = (
        MiraxJpegDecoder(),
        MiraxBmpDecoder(),
        MiraxPngDecoder(),
        MiraxJpegXrDecoder(),
        MiraxJpeg2000Decoder(),
    )
    """The decoders for the listed formats; decoders hold no state, so they are
    shared."""

    @classmethod
    def for_image_format(cls, image_format: str) -> MiraxDecoder:
        """Return the decoder for tiles of an IMAGE_FORMAT.

        Parameters
        ----------
        image_format: str
            The slide's IMAGE_FORMAT.

        Returns
        -------
        MiraxDecoder
            The decoder for the format, or one that recognizes the blob's format
            itself if the format is not known.
        """
        for decoder in cls._DECODERS:
            if image_format in decoder.image_formats:
                return decoder
        return MiraxSniffingDecoder()

    @classmethod
    def for_blob(cls, blob: bytes) -> MiraxDecoder:
        """Return the decoder for a blob, recognized by its magic bytes.

        Parameters
        ----------
        blob: bytes
            The stored bytes.

        Returns
        -------
        MiraxDecoder
            The decoder for the blob's format, or one that recognizes the format
            itself if no magic matches.
        """
        for decoder in cls._DECODERS:
            if decoder.magic is not None and blob.startswith(decoder.magic):
                return decoder
        return MiraxSniffingDecoder()
