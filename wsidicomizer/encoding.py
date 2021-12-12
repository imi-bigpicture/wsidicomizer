#    Copyright 2021 SECTRA AB
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

import io
from abc import ABCMeta, abstractmethod
from typing import Optional, Union

import numpy as np
from PIL import Image
from pydicom.uid import JPEG2000, UID, JPEG2000Lossless, JPEGBaseline8Bit


class Encoder(metaclass=ABCMeta):
    """Abstract class for an image encoder."""

    @property
    @abstractmethod
    def transfer_syntax(self) -> UID:
        """Should return correspodning transfer syntax for encoded data."""
        raise NotImplementedError

    @property
    @abstractmethod
    def quality(self) -> Union[int, float]:
        """Should return quality setting of encoder."""
        raise NotImplementedError

    @abstractmethod
    def encode(self, data: Union[Image.Image, np.ndarray]) -> bytes:
        """Should return data as encoded bytes."""
        raise NotImplementedError


class JpegEncoder(Encoder):
    """Encoder for JPEG."""

    def __init__(
        self,
        quality: int = 90,
        subsampling: Optional[str] = '422'
    ) -> None:
        """Creates a JPEG encoder with specified settings.

        Parameters
        ----------
        quality: int = 90
            The encoding quality. To not use higher than 95.
        subsampling: Optional[str] = '422'
            Subsampling option.

        """
        if subsampling == '444':
            self._subsampling = 0
        elif subsampling == '422':
            self._subsampling = 1
        elif subsampling == '420':
            self._subsampling = 2
        else:
            raise ValueError("Supsampling should be '444', '422', or '420'")
        self._quality = quality
        self._outcolorspace = 'YCBCR'

    @property
    def transfer_syntax(self) -> UID:
        """Transfer syntax of encoder."""
        return JPEGBaseline8Bit

    @property
    def quality(self) -> int:
        """Quality setting of encoder"""
        return self._quality

    def encode(self, data: Union[Image.Image, np.ndarray]) -> bytes:
        """Encodes data as JPEG.

        Parameters
        ----------
        data: Union[Image.Image, np.ndarray
            Data to encode.

        Returns
        ----------
        bytes:
            JPEG bytes.
        """
        if isinstance(data, np.ndarray):
            data = Image.fromarray(data)
        with io.BytesIO() as buffer:
            data.save(
                buffer,
                format='JPEG',
                quality=self.quality,
                subsampling=self._subsampling
            )
            return buffer.getvalue()


class Jpeg2000Encoder(Encoder):
    START_TAGS = bytes([0xFF, 0x4F, 0xFF, 0x51])

    def __init__(
        self,
        quality: float = 2
    ) -> None:
        """Creates a JPEG2000 encoder with specified settings.

        Parameters
        ----------
        quality: float = 2. Use < 1 for lossless.
            The encoding quality.


        """
        self._quality = quality
        if self.quality < 1:
            self._transfer_syntax = JPEG2000Lossless
        else:
            self._transfer_syntax = JPEG2000

    @property
    def transfer_syntax(self) -> UID:
        """Transfer syntax of encoder."""
        return self._transfer_syntax

    @property
    def quality(self) -> float:
        """Quality setting of encoder"""
        return self._quality

    def encode(self, data: Union[Image.Image, np.ndarray]) -> bytes:
        """Encodes data as JPEG2000.

        Parameters
        ----------
        data: Union[Image.Image, np.ndarray
            Data to encode.

        Returns
        ----------
        bytes:
            JPEG2000 bytes.
        """
        if isinstance(data, np.ndarray):
            data = Image.fromarray(data)
        with io.BytesIO() as buffer:
            data.save(
                buffer,
                format='JPEG2000',
                quality=self.quality
            )
            frame = buffer.getvalue()
        # PIL encodes in jp2, find start of j2k and return from there.
        start_index = frame.find(self.START_TAGS)
        return frame[start_index:]


def create_encoder(
    format: str,
    quality: float,
    subsampling: Optional[str] = None
) -> Encoder:
    """Creates an encoder with specified settings.

    Parameters
    ----------
    format: str
        Format for encoder, either 'jpeg' or 'jpeg2000.
    quality: float
        The encoding quality.
    subsampling: Optional[str] = None
        Subsampling setting (for jpeg).
    Returns
    ----------
    Enocer
        Encoder for settings.
    """
    if format == 'jpeg':
        return JpegEncoder(
            quality=int(quality),
            subsampling=subsampling
        )
    elif format == 'jpeg2000':
        return Jpeg2000Encoder(
            quality=quality
        )
    raise ValueError("Encoder format must be 'jpeg' or 'jpeg2000'")
