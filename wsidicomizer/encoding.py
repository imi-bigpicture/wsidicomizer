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
    @property
    @abstractmethod
    def transfer_syntax(self) -> UID:
        raise NotImplementedError

    @property
    @abstractmethod
    def quality(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def encode(self, data: np.ndarray) -> bytes:
        raise NotImplementedError


class JpegEncoder(Encoder):
    def __init__(
        self,
        quality: int = 90,
        subsampling: Optional[str] = '422',
        colorspace: Optional[Union[int, str]] = None
    ) -> None:
        self._quality = quality
        self._subsampling = subsampling
        self._colorspace = colorspace
        self._outcolorspace = 'YCBCR'

    @property
    def transfer_syntax(self) -> UID:
        return JPEGBaseline8Bit

    @property
    def quality(self) -> int:
        return self._quality

    def encode(self, data: np.ndarray) -> bytes:
        if data.dtype != np.dtype(np.uint8):
            data = (data * 255 / np.iinfo(data.dtype).max).astype(np.uint8)
        return jpeg8_encode(
            data,
            level=self._quality,
            colorspace=self._colorspace,
            outcolorspace=self._outcolorspace,
            subsampling=self._subsampling
        )


class Jpeg2000Encoder(Encoder):
    def __init__(
        self,
        quality: int = 90,
    ) -> None:
        self._quality = quality
        if self.quality == 100:
            self._transfer_syntax = JPEG2000Lossless
        else:
            self._transfer_syntax = JPEG2000

    @property
    def transfer_syntax(self) -> UID:
        return self._transfer_syntax

    @property
    def quality(self) -> int:
        return self._quality

    def encode(self, data: np.ndarray) -> bytes:
        return jpeg2k_encode(
            data,
            codecformat="J2K",
            level=self._quality
        )


def create_encoder(
    format: str,
    quality: int,
    subsampling: Optional[str] = None,
    colorspace: Optional[Union[int, str]] = None
) -> Encoder:
    if format == 'jpeg':
        return JpegEncoder(
            quality=quality,
            subsampling=subsampling,
            colorspace=colorspace
        )
    elif format == 'jpeg2000':
        return Jpeg2000Encoder(
            quality=quality
        )
    raise ValueError("Encoder format must be 'jpeg' or 'jpeg2000'")
