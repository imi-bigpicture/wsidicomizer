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

from abc import ABCMeta, abstractmethod
from typing import Union, Optional
import numpy as np
from imagecodecs import jpeg2k_encode, jpeg8_encode
from pydicom.uid import UID, JPEGBaseline8Bit, JPEG2000Lossless, JPEG2000


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
    def encode(
        self,
        data: np.ndarray
    ) -> bytes:
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
        self._quality = quality
        self._subsampling = subsampling
        self._outcolorspace = 'YCBCR'

    @property
    def transfer_syntax(self) -> UID:
        """Transfer syntax of encoder."""
        return JPEGBaseline8Bit

    @property
    def quality(self) -> int:
        """Quality setting of encoder"""
        return self._quality

    def encode(
        self,
        data: np.ndarray
    ) -> bytes:
        """Encodes data as JPEG. Converts data to uint8 before conversion.

        Parameters
        ----------
        data: np.ndarray
            Data to encode.

        Returns
        ----------
        bytes:
            JPEG bytes.
        """
        if data.dtype != np.dtype(np.uint8):
            data = (data * 255 / np.iinfo(data.dtype).max).astype(np.uint8)
        return jpeg8_encode(
            data,
            level=self._quality,
            outcolorspace=self._outcolorspace,
            subsampling=self._subsampling
        )


class Jpeg2000Encoder(Encoder):
    def __init__(
        self,
        quality: float = 20
    ) -> None:
        """Creates a JPEG2000 encoder with specified settings.

        Parameters
        ----------
        quality: float = 20. Use < 1 for lossless.
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

    def encode(
        self,
        data: np.ndarray
    ) -> bytes:
        """Encodes data as JPEG2000.

        Parameters
        ----------
        data: np.ndarray
            Numpy array of data to encode.

        Returns
        ----------
        bytes
            JPEG2000 bytes.
        """
        return jpeg2k_encode(
            data,
            level=self._quality,
            codecformat='J2K',
        )


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
