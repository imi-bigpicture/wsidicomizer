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

"""Module containing a base ImageData implementation suitable for use with non-DICOM
files."""

from typing import List, Optional

import numpy as np
from PIL import Image as Pillow
from PIL.Image import Image
from wsidicom import ImageData
from wsidicom.codec import Encoder
from wsidicom.geometry import PointMm, Size
from wsidicom.metadata import ImageCoordinateSystem, LossyCompression


class DicomizerImageData(ImageData):
    """
    Base class for Dicomizer image data. Subclasses should implement all the abstract
    methods and properties in the base ImageData-class.
    """

    _default_z = None

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        """Return a default ImageCoordinateSystem."""
        return ImageCoordinateSystem(PointMm(0, 0), 90)

    @property
    def bits(self) -> int:
        return self.encoder.bits

    @property
    def lossy_compression(
        self,
    ) -> Optional[List[LossyCompression]]:
        """Return None as image compression is for most format not known."""
        return None

    @property
    def transcoder(self) -> Optional[Encoder]:
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
        if self._blank_encoded_frame_size != size:
            frame = np.full(
                size.to_tuple() + (3,), self.blank_color, dtype=np.dtype(np.uint8)
            )
            self._blank_encoded_frame = self.encoder.encode(frame)
            self._blank_encoded_frame_size = size
        return self._blank_encoded_frame

    def _get_blank_decoded_frame(self, size: Size) -> Image:
        """Return cached blank decoded frame for size, or create frame if
        cached frame not available or of wrong size.

        Parameters
        ----------
        size: Size
            Size of frame to get.

        Returns
        ----------
        bytes
            Decoded blank frame.
        """
        if self._blank_decoded_frame is None or self._blank_decoded_frame_size != size:
            frame = Pillow.new("RGB", size.to_tuple(), self.blank_color)
            self._blank_decoded_frame = frame
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
        if np.all(tile[corners_rgb] == background):
            if np.all(tile == background):
                return True
        return False
