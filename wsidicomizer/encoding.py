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

"""
Modulule containing image encodes that can be used to encode raw or decoded images
using implemented image encoders.
"""

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
        """Should return corresponding transfer syntax for encoded data."""
        raise NotImplementedError

    @property
    @abstractmethod
    def quality(self) -> Union[int, float]:
        """Should return quality setting of encoder."""
        raise NotImplementedError

    @abstractmethod
    def photometric_interpretation(self, channels: int) -> str:
        raise NotImplementedError()

    @abstractmethod
    def encode(self, data: np.ndarray) -> bytes:
        """Should return data as encoded bytes."""
        raise NotImplementedError()

    @classmethod
    def create_encoder(
        cls, format: str, quality: float, subsampling: Optional[str] = None
    ) -> "Encoder":
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
        if format == "jpeg":
            return JpegEncoder(quality=int(quality), subsampling=subsampling)
        elif format == "jpeg2000":
            return Jpeg2000Encoder(quality=quality)
        raise ValueError("Encoder format must be 'jpeg' or 'jpeg2000'")


class JpegEncoder(Encoder):
    """Encoder for JPEG."""

    def __init__(self, quality: int = 90, subsampling: Optional[str] = "420") -> None:
        """Creates a JPEG encoder with specified settings.

        Parameters
        ----------
        quality: int = 90
            The encoding quality. Recommended to not use higher than 95.
        subsampling: Optional[str] = '420'
            Subsampling option. Use '444' for no subsampling, '422' for 2x1
            subsampling, and '420' for 2x2 subsampling.
        """
        self._quality = quality
        if subsampling not in ["444", "422", "420"]:
            raise NotImplementedError(
                f"Only '444', '422' and '420' subsampling options implemented."
            )
        self._subsampling = subsampling

    @property
    def transfer_syntax(self) -> UID:
        """Transfer syntax of encoder."""
        return JPEGBaseline8Bit

    def photometric_interpretation(self, channels: int) -> str:
        if channels == 1:
            return "MONOCHROME2"
        elif channels == 3:
            return "YBR_FULL_422"
        raise ValueError()

    @property
    def quality(self) -> int:
        """Quality setting of encoder"""
        return self._quality

    @property
    def subsampling(self) -> Optional[str]:
        """Subsampling of encoder"""
        return self._subsampling

    def encode(self, data: np.ndarray) -> bytes:
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
            data = (255 * (data / np.iinfo(data.dtype).max)).astype(np.uint8)
        return jpeg8_encode(data, level=self._quality, subsampling=self._subsampling)


class Jpeg2000Encoder(Encoder):
    def __init__(self, quality: float = 20.0) -> None:
        """Creates a JPEG2000 encoder with specified settings.

        Parameters
        ----------
        quality: float = 20.0.
            The encoding quality as peak signal to noise (PSNR). Use < 1 or > 1000 for
            lossless quality. Up to 60 gives acceptable results.

        """
        self._quality = quality
        if self.quality < 1 or self.quality > 1000:
            self._transfer_syntax = JPEG2000Lossless
        else:
            self._transfer_syntax = JPEG2000

    def photometric_interpretation(self, channels: int) -> str:
        if channels == 1:
            return "MONOCRHOME2"
        elif channels == 3:
            if self.transfer_syntax == JPEG2000Lossless:
                return "YBR_RCT"
            return "YBR_ICT"
        raise ValueError()

    @property
    def transfer_syntax(self) -> UID:
        """Transfer syntax of encoder."""
        return self._transfer_syntax

    @property
    def quality(self) -> float:
        """Quality setting of encoder"""
        return self._quality

    def encode(self, data: np.ndarray) -> bytes:
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
            codecformat="J2K",
        )
