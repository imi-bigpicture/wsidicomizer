from abc import ABCMeta, abstractmethod
from typing import Union

import numpy as np
import pydicom
from imagecodecs import jpeg2k_encode, jpeg8_encode
from pydicom.uid import UID as Uid


class Encoder(metaclass=ABCMeta):
    @property
    @abstractmethod
    def transfer_syntax(self) -> Uid:
        raise NotImplementedError

    @property
    @abstractmethod
    def quality(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def encode(self, data: np.ndarray):
        raise NotImplementedError


class JpegEncoder(Encoder):
    def __init__(
        self,
        quality: int = 90,
        subsampling: str = '422',
        colorspace: Union[int, str] = None
    ) -> None:
        self._quality = quality
        self._subsampling = subsampling
        self._colorspace = colorspace
        self._outcolorspace = 'YCBCR'

    @property
    def transfer_syntax(self) -> Uid:
        return pydicom.uid.JPEGBaseline8Bit

    @property
    def quality(self) -> int:
        return self._quality

    def encode(self, data: np.ndarray):
        if data.dtype != np.uint8:
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
            self._transfer_syntax = pydicom.uid.JPEG2000Lossless
        else:
            self._transfer_syntax = pydicom.uid.JPEG2000

    @property
    def transfer_syntax(self) -> Uid:
        return self._transfer_syntax

    @property
    def quality(self) -> int:
        return self._quality

    def encode(self, data: np.ndarray):
        return jpeg2k_encode(
            data,
            level=self._quality
        )


def create_encoder(
    format: str,
    quality: int,
    subsampling: str = None,
    colorspace: Union[int, str] = None
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
