from abc import ABCMeta, abstractmethod
from typing import Union

import numpy as np
import pydicom
from imagecodecs import jpeg2k_encode, jpeg8_encode
# from opentile.turbojpeg_patch import find_turbojpeg_path
from pydicom.uid import UID as Uid
# from turbojpeg import (TJPF_ABGR, TJPF_ARGB, TJPF_BGR, TJPF_BGRA, TJPF_BGRX,
#                        TJPF_GRAY, TJPF_RGB, TJPF_RGBA, TJPF_RGBX, TJPF_XBGR,
#                        TJPF_XRGB, TJSAMP_411, TJSAMP_420, TJSAMP_422,
#                        TJSAMP_444, TJSAMP_GRAY, TurboJPEG)


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


# class TurboJpegEncoder(Encoder):
#     def __init__(
#         self,
#         quality: int = 90,
#         subsampling: str = '422',
#         colorspace: str = 'RGB'
#     ) -> None:
#         self._jpeg = TurboJPEG(str(find_turbojpeg_path()))
#         self._quality = quality
#         if subsampling == '444':
#             self._subsampling = TJSAMP_444
#         elif subsampling == '422':
#             self._subsampling = TJSAMP_422
#         elif subsampling == '420':
#             self._subsampling = TJSAMP_420
#         elif subsampling == '411':
#             self._subsampling = TJSAMP_411
#         elif subsampling == 'GRAY':
#             self._subsampling = TJSAMP_GRAY
#         else:
#             raise ValueError("Unkown subsampling option")

#         if colorspace == 'RGB':
#             self._colorspace = TJPF_RGB
#         elif colorspace == 'BGR':
#             self._colorspace = TJPF_BGR
#         elif colorspace == 'RGBX':
#             self._colorspace = TJPF_RGBX
#         elif colorspace == 'BGRX':
#             self._colorspace = TJPF_BGRX
#         elif colorspace == 'XBGR':
#             self._colorspace = TJPF_XBGR
#         elif colorspace == 'XRGB':
#             self._colorspace = TJPF_XRGB
#         elif colorspace == 'GRAY':
#             self._colorspace = TJPF_GRAY
#         elif colorspace == 'RGBA':
#             self._colorspace = TJPF_RGBA
#         elif colorspace == 'BGRA':
#             self._colorspace = TJPF_BGRA
#         elif colorspace == 'ABGR':
#             self._colorspace = TJPF_ABGR
#         elif colorspace == 'ARGB':
#             self._colorspace = TJPF_ARGB
#         else:
#             raise ValueError("Unkown colorspace option")
#         print(self._colorspace)

#     @property
#     def transfer_syntax(self) -> Uid:
#         return pydicom.uid.JPEGBaseline8Bit

#     @property
#     def quality(self) -> int:
#         return self._quality

#     def encode(self, data: np.ndarray):
#         if data.dtype != np.uint8:
#             print("scaling data")
#             data = (data * 255 / np.iinfo(data.dtype).max).astype(np.uint8)
#         return self._jpeg.encode(
#             data,
#             quality=self._quality,
#             pixel_format=self._colorspace,
#             jpeg_subsample=self._subsampling
#         )


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
