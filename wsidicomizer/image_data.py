#    Copyright 2021, 2022, 2023 SECTRA AB
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

"""Base ImageData classes for non-DICOM source adapters."""

from abc import abstractmethod

import numpy as np
from wsidicom import ImageData
from wsidicom.codec import Encoder
from wsidicom.geometry import Region, Size
from wsidicom.metadata import ImageCoordinateSystem, LossyCompression


class BaseDicomizerImageData(ImageData):
    """
    Base class for Dicomizer image data. Subclasses should implement all the abstract
    methods and properties in the base ImageData-class.
    """

    _blank_encoded_frame: bytes | None = None
    _blank_encoded_frame_size: Size | None = None
    _blank_decoded_frame: np.ndarray | None = None
    _blank_decoded_frame_size: Size | None = None

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem | None:
        """Return a default ImageCoordinateSystem."""
        return None

    @property
    def bits(self) -> int:
        return self.encoder.bits

    @property
    def lossy_compression(
        self,
    ) -> list[LossyCompression] | None:
        """Return None as image compression is for most format not known."""
        return None

    @property
    def transcoder(self) -> Encoder | None:
        """Return encoder as for most format transcoding is used."""
        return self.encoder

    def _encode(self, image_data: np.ndarray) -> bytes:
        """Return image data encoded in jpeg using set quality and subsample
        options.

        Parameters
        ----------
        image_data: np.ndarray
            Image data to encode.

        Returns
        ----------
        bytes
            Jpeg bytes.
        """
        return self.encoder.encode(image_data)

    def _get_blank_encoded_frame(self, size: Size) -> bytes:
        """Return cached blank encoded frame for size, or create frame if
        cached frame not available or of wrong size.

        Parameters
        ----------
        size: Size
            Size of frame to get.

        Returns
        ----------
        bytes
            Encoded blank frame.
        """
        if self._blank_encoded_frame is None or self._blank_encoded_frame_size != size:
            frame = np.full(
                size.to_tuple() + (3,), self.blank_color, dtype=np.dtype(np.uint8)
            )
            self._blank_encoded_frame = self.encoder.encode(frame)
            self._blank_encoded_frame_size = size
        return self._blank_encoded_frame

    def _get_blank_decoded_frame(self, size: Size) -> np.ndarray:
        """Return the cached blank frame pixels for the size.

        Parameters
        ----------
        size: Size
            Size of frame to get.

        Returns
        ----------
        np.ndarray
            Decoded blank frame as ``(rows, columns, 3)``.
        """
        if self._blank_decoded_frame is None or self._blank_decoded_frame_size != size:
            self._blank_decoded_frame = np.full(
                size.to_tuple() + (3,), self.blank_color, dtype=np.dtype(np.uint8)
            )
            self._blank_decoded_frame_size = size
        return self._blank_decoded_frame

    def _detect_blank_tile(self, tile: np.ndarray) -> bool:
        """Detect if tile is a blank tile, i.e. is filled with background color.
        First checks if the corners  before checking whole tile.

        Parameters
        ----------
        tile: np.ndarray
            Tile to check if blank.

        Returns
        ----------
        bool
            True if tile is blank.
        """

        TOP = RIGHT = -1
        BOTTOM = LEFT = 0
        CORNERS_Y = [BOTTOM, BOTTOM, TOP, TOP]
        CORNERS_X = [LEFT, RIGHT, LEFT, RIGHT]
        background = np.array(self.blank_color)
        corners_rgb = np.ix_(CORNERS_X, CORNERS_Y)
        return bool(
            np.all(tile[corners_rgb] == background) and np.all(tile == background)
        )


class PixelImageData(BaseDicomizerImageData):
    """ImageData whose source can only produce decoded pixel data.

    The underlying source returns decoded pixels — there are no
    source-encoded bytes to pass through, so producing an encoded tile
    requires re-encoding.

    Concrete subclasses implement ``read_region`` either as a native call
    (for pyramidal/tiled sources) or as an in-memory crop of a pre-decoded
    image (for single-image label/overview/thumbnail sources). Pair with
    ``PixelWsiInstance`` so reads route through ``read_region`` instead of
    per-tile stitching.
    """

    @abstractmethod
    def read_region(self, region: Region, z: float, path: str) -> np.ndarray:
        """Read the pixels of a region from the source.

        The region-read primitive. Pixel sources decode to numpy and implement
        this; Pillow, when needed, is derived at the read boundary.

        Parameters
        ----------
        region: Region
            Pixel region to read.
        z: float
            Z coordinate.
        path: str
            Optical path.

        Returns
        -------
        np.ndarray
            The region as ``(rows, columns)`` or ``(rows, columns, samples)``.
        """
        raise NotImplementedError()
