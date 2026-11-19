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

"""Image data for a pyramid level in an Olympus VSI slide."""

import math
from dataclasses import dataclass
from functools import cached_property

import numpy as np
from opentile.jpeg import Jpeg, JpegProcess
from opentile.jpeg2000 import Jpeg2000
from pydicom.uid import JPEG2000, UID, JPEG2000Lossless, JPEGBaseline8Bit
from wsidicom.codec import (
    Decoder,
    Encoder,
    Jpeg2kSettings,
    JpegSettings,
    LossyCompressionIsoStandard,
)
from wsidicom.codec.settings import Channels, Settings, Subsampling
from wsidicom.errors import WsiDicomNotFoundError
from wsidicom.geometry import Point, Size, SizeMm
from wsidicom.metadata import ImageCoordinateSystem, LossyCompression

from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.sources.vsi.ets import EtsFile

J2K_SOC_SIZ = bytes.fromhex("ff4fff51")
JPEG_SOI = bytes.fromhex("ffd8")


@dataclass(frozen=True)
class TileFormat:
    """The DICOM description of the tiles of a level."""

    transfer_syntax: UID
    samples_per_pixel: int
    bits: int
    photometric_interpretation: str

    @classmethod
    def from_ets(cls, ets: EtsFile, level: int) -> "TileFormat":
        """Return the format of the tiles of a level, read from a stored tile.

        Olympus stores JPEG 2000, JPEG, and uncompressed tiles. The `.ets`
        header has no identified codec field, so the tile itself is the only
        description of the format, and one that can not be out of step with the
        data.
        """
        tile = ets.get_any_tile(level)
        if tile is None:
            raise ValueError(f"Level {level} of {ets} has no tiles.")
        if tile.startswith(J2K_SOC_SIZ):
            return cls._from_jpeg_2000(tile, ets)
        if tile.startswith(JPEG_SOI):
            return cls._from_jpeg(tile, ets)
        raise NotImplementedError(
            f"Tiles of {ets} are of an unsupported codec, starting {tile[:4].hex()}. "
            "Only JPEG 2000 and JPEG tiles can be read."
        )

    @classmethod
    def _from_jpeg_2000(cls, tile: bytes, ets: EtsFile) -> "TileFormat":
        info = Jpeg2000.parse(tile)
        if info is None or info.extended:
            raise NotImplementedError(
                f"Only plain JPEG 2000 Part 1 tiles are supported in {ets}."
            )
        if info.components == 1:
            photometric_interpretation = "MONOCHROME2"
        elif not info.uses_mct:
            photometric_interpretation = "RGB"
        else:
            # The codestream applies the multiple component transform, which
            # PS3.5 8.2.4 requires to be signalled as YBR_RCT or YBR_ICT.
            photometric_interpretation = "YBR_RCT" if info.reversible else "YBR_ICT"
        return cls(
            JPEG2000Lossless if info.reversible else JPEG2000,
            info.components,
            info.bit_depth,
            photometric_interpretation,
        )

    @classmethod
    def _from_jpeg(cls, tile: bytes, ets: EtsFile) -> "TileFormat":
        info = Jpeg.info(tile)
        if info.process != JpegProcess.BASELINE or info.bit_depth != 8:
            raise NotImplementedError(
                f"Only baseline 8 bit JPEG tiles are supported in {ets}, got "
                f"{info.process} at {info.bit_depth} bits."
            )
        if info.components == 1:
            photometric_interpretation = "MONOCHROME2"
        elif info.rgb_signalled:
            photometric_interpretation = "RGB"
        elif info.subsampling == (1, 1):
            photometric_interpretation = "YBR_FULL"
        else:
            photometric_interpretation = "YBR_FULL_422"
        return cls(
            JPEGBaseline8Bit,
            info.components,
            info.bit_depth,
            photometric_interpretation,
        )

    def blank_encoder(self) -> Encoder:
        """Return an encoder that produces blank frames in this format.

        A sparse level has no tile outside the scanned region, but DICOM
        `TILED_FULL` requires every frame, so the missing ones are emitted as a
        blank frame. That frame must be in the same transfer syntax and
        photometric interpretation as the passed-through tiles, or the instance
        is inconsistent.
        """
        channels = {
            "MONOCHROME2": Channels.GRAYSCALE,
            "RGB": Channels.RGB,
        }.get(self.photometric_interpretation, Channels.YBR)
        if self.transfer_syntax == JPEGBaseline8Bit:
            subsampling = (
                Subsampling.R422
                if self.photometric_interpretation == "YBR_FULL_422"
                else Subsampling.R444
            )
            settings: Settings = JpegSettings(
                bits=self.bits, channels=channels, subsampling=subsampling
            )
        else:
            lossless = self.transfer_syntax == JPEG2000Lossless
            settings = Jpeg2kSettings(
                levels=[0] if lossless else [80],
                bits=self.bits,
                channels=channels,
            )
        return Encoder.create_for_settings(settings)


class VsiLevelImageData(BaseDicomizerImageData):
    """A pyramid level of an Olympus VSI slide, read from its `.ets` container.

    The tiles are complete JPEG 2000 or JPEG codestreams of uniform size with no
    overlap, so they are passed through to DICOM unchanged.
    """

    def __init__(
        self,
        ets: EtsFile,
        level: int,
        encoder: Encoder,
        base_pixel_spacing: SizeMm | None,
        image_coordinate_system: ImageCoordinateSystem | None,
    ):
        """Wrap a level of an EtsFile as ImageData.

        Parameters
        ----------
        ets: EtsFile
            Opened `.ets` container.
        level: int
            Pyramid level in the container to wrap.
        encoder: Encoder
            Ignored. Blank frames use an encoder matching the tiles so a sparse
            level stays consistent; tiles themselves are passed through.
        base_pixel_spacing: SizeMm | None
            Pixel spacing of the base level, or None if not known.
        image_coordinate_system: ImageCoordinateSystem | None
            Image coordinate system to use.
        """
        self._format = TileFormat.from_ets(ets, level)
        super().__init__(self._format.blank_encoder())
        self._ets = ets
        self._level = level
        self._tile_size = ets.tile_size
        # Each level pads its tile grid separately, so a level covers up to a
        # tile more than half of the previous one. Sizing a level by its grid
        # would make the levels no exact factor two apart, which viewers see as
        # the image drifting towards the bottom right at each zoom step. Size it
        # from the base level halved instead, rounding up.
        base_size = ets.image_size or ets.tiled_sizes[0] * ets.tile_size
        downsample = 2**level
        self._image_size = Size(
            math.ceil(base_size.width / downsample),
            math.ceil(base_size.height / downsample),
        )
        if base_pixel_spacing is not None:
            self._pixel_spacing = base_pixel_spacing * 2**level
        else:
            self._pixel_spacing = None
        self._image_coordinate_system = image_coordinate_system

    def __str__(self) -> str:
        return f"{type(self).__name__} for level {self._level} of {self._ets}"

    @property
    def transfer_syntax(self) -> UID:
        return self._format.transfer_syntax

    @property
    def image_size(self) -> Size:
        """Size of the level in pixels, the base level size halved per level.

        When the `.ets` header records the unpadded base size it is used;
        otherwise (the older writer) it falls back to the padded tile grid, so
        up to a tile of background is included at the right and bottom edges.
        """
        return self._image_size

    @property
    def tile_size(self) -> Size:
        return self._tile_size

    @property
    def pixel_spacing(self) -> SizeMm | None:
        return self._pixel_spacing

    @property
    def imaged_size(self) -> SizeMm | None:
        if self._pixel_spacing is None:
            return None
        return self._pixel_spacing * self._image_size

    @property
    def samples_per_pixel(self) -> int:
        return self._format.samples_per_pixel

    @property
    def bits(self) -> int:
        return self._format.bits

    @property
    def photometric_interpretation(self) -> str:
        return self._format.photometric_interpretation

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem | None:
        return self._image_coordinate_system

    @property
    def thread_safe(self) -> bool:
        """Not thread safe as tiles are read from a shared file handle."""
        return False

    @property
    def transcoder(self) -> Encoder | None:
        """Return None as tiles are passed through."""
        return None

    @property
    def lossy_compression(self) -> list[LossyCompression] | None:
        iso = LossyCompressionIsoStandard.transfer_syntax_to_iso(self.transfer_syntax)
        if iso is None:
            return None
        uncompressed_size = (
            self._image_size.area * self.samples_per_pixel * self.bits // 8
        )
        ratio = round(uncompressed_size / self._ets.compressed_size(self._level), 2)
        return [LossyCompression(iso, ratio)]

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        self._validate(z, path)
        data = self._ets.get_tile(self._level, tile)
        if data is None:
            return self._get_blank_encoded_frame(self.tile_size)
        return data

    def get_decoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str,
        cache: bool = True,
    ) -> np.ndarray:
        self._validate(z, path)
        data = self._ets.get_tile(self._level, tile_point)
        if data is None:
            return self._get_blank_decoded_frame(self.tile_size)
        return self._decoder.decode(data)

    @cached_property
    def _decoder(self) -> Decoder:
        return Decoder.create(
            self.transfer_syntax,
            self.samples_per_pixel,
            self.bits,
            self.tile_size,
            self.photometric_interpretation,
        )

    def _validate(self, z: float, path: str) -> None:
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f"focal plane {z}", str(self))
        if path not in self.optical_paths:
            raise WsiDicomNotFoundError(f"optical path {path}", str(self))
