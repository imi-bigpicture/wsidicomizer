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

"""Image data for opentile compatible file."""

from typing import Iterable, Iterator, List, Optional

from opentile.tiff_image import TiffImage
from PIL import Image as Pillow
from PIL.Image import Image
from pydicom.uid import JPEG2000, UID, JPEG2000Lossless, JPEGBaseline8Bit
from tifffile.tifffile import COMPRESSION, PHOTOMETRIC
from wsidicom.codec import Encoder
from wsidicom.geometry import Point, Size, SizeMm
from wsidicom.metadata import Image as ImageMetadata
from wsidicom.metadata import ImageCoordinateSystem

from wsidicomizer.image_data import DicomizerImageData


class OpenTileImageData(DicomizerImageData):
    def __init__(
        self,
        tiff_image: TiffImage,
        encoder: Encoder,
        force_transcoding: bool = False,
    ):
        """Wraps a TiffImage to ImageData.

        Parameters
        ----------
        tiff_image: TiffImage
            TiffImage to wrap.
        encoded: Encoder
            Encoder to use.
        force_transcoding: bool
            Force transcoding of image data.
        """
        super().__init__(encoder)
        self._tiff_image = tiff_image

        self._needs_transcoding = (
            not self.is_supported_transfer_syntax() or force_transcoding
        )
        if self.needs_transcoding:
            self._transfer_syntax = self.encoder.transfer_syntax
        else:
            self._transfer_syntax = self.get_transfer_syntax()
        self._image_size = Size(*self._tiff_image.image_size.to_tuple())
        self._tile_size = Size(*self._tiff_image.tile_size.to_tuple())
        self._tiled_size = Size(*self._tiff_image.tiled_size.to_tuple())

    def __str__(self) -> str:
        return f"{type(self).__name__} for page {self._tiff_image}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._tiff_image})"

    @property
    def transfer_syntax(self) -> UID:
        """The uid of the transfer syntax of the image."""
        return self._transfer_syntax

    @property
    def needs_transcoding(self) -> bool:
        """Return true if image data requires transcoding for Dicom
        compatibility."""
        return self._needs_transcoding

    @property
    def native_compression(self) -> COMPRESSION:
        """Return compression method used in image data."""
        return self._tiff_image.compression

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @property
    def focal_planes(self) -> List[float]:
        """Focal planes available in the image defined in um."""
        return [self._tiff_image.focal_plane]

    @property
    def optical_paths(self) -> List[str]:
        """Optical paths available in the image."""
        return [self._tiff_image.optical_path]

    @property
    def suggested_minimum_chunk_size(self) -> int:
        """Return suggested minimum chunk size for optimal performance with
        get_encoeded_tiles()."""
        return self._tiff_image.suggested_minimum_chunk_size

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return self._tiff_image.pyramid_index

    @property
    def photometric_interpretation(self) -> str:
        if self.needs_transcoding:
            return self.encoder.photometric_interpretation
        if self._tiff_image.photometric_interpretation == PHOTOMETRIC.YCBCR:
            if self.transfer_syntax == JPEGBaseline8Bit:
                return "YBR_FULL_422"
            elif self.transfer_syntax == JPEG2000:
                return "YBR_ICT"
            elif self.transfer_syntax == JPEG2000Lossless:
                return "YBR_RCT"
        elif self._tiff_image.photometric_interpretation == PHOTOMETRIC.RGB:
            return "RGB"
        elif self._tiff_image.photometric_interpretation == (PHOTOMETRIC.MINISBLACK):
            return "MONOCHROME2"
        raise NotImplementedError(
            "Non-implemented photometric interpretation. ",
            self._tiff_image.photometric_interpretation,
        )

    @property
    def samples_per_pixel(self) -> int:
        return self._tiff_image.samples_per_pixel

    def _get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
        """Return image bytes for tile. Returns transcoded tile if
        non-supported encoding.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        z: float
            Focal plane of tile to get.
        path: str
            Optical path of tile to get.

        Returns
        ----------
        bytes
            Tile bytes.
        """
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError()
        if self.needs_transcoding:
            decoded_tile = self._tiff_image.get_decoded_tile(tile.to_tuple())
            return self.encoder.encode(decoded_tile)
        return self._tiff_image.get_tile(tile.to_tuple())

    def _get_decoded_tile(self, tile: Point, z: float, path: str) -> Image:
        """Return Image for tile.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        z: float
            Focal plane of tile to get.
        path: str
            Optical path of tile to get.

        Returns
        ----------
        Image.Image
            Tile as Image.
        """
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        return Pillow.fromarray(self._tiff_image.get_decoded_tile(tile.to_tuple()))

    def _get_encoded_tiles(
        self, tiles: Iterable[Point], z: float, path: str
    ) -> Iterator[bytes]:
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        tiles_tuples = [tile.to_tuple() for tile in tiles]
        if not self.needs_transcoding:
            return self._tiff_image.get_tiles(tiles_tuples)
        decoded_tiles = self._tiff_image.get_decoded_tiles(tiles_tuples)
        return (self.encoder.encode(tile) for tile in decoded_tiles)

    def close(self) -> None:
        self._tiff_image.close()

    def is_supported_transfer_syntax(self) -> bool:
        """Return true if image data is encoded with Dicom-supported transfer
        syntax."""
        try:
            self.get_transfer_syntax()
            return True
        except NotImplementedError:
            return False

    def get_transfer_syntax(self) -> UID:
        """Return transfer syntax (Uid) for compression type in image data."""
        compression = self.native_compression
        if compression == COMPRESSION.JPEG:
            return JPEGBaseline8Bit
        elif compression == COMPRESSION.APERIO_JP2000_RGB:
            return JPEG2000
        raise NotImplementedError(f"Not supported compression {compression}")


class OpenTileLevelImageData(OpenTileImageData):
    def __init__(
        self,
        tiff_image: TiffImage,
        image_metadata: ImageMetadata,
        merged_metadata: ImageMetadata,
        encoder: Encoder,
        force_transcoding: bool = False,
    ):
        super().__init__(tiff_image, encoder, force_transcoding)
        if (
            merged_metadata.pixel_spacing is not None
            and merged_metadata.pixel_spacing != image_metadata.pixel_spacing
        ):
            # Override pixel spacing
            self._pixel_spacing = merged_metadata.pixel_spacing * int(
                2**self._tiff_image.pyramid_index
            )
        elif self._tiff_image.pixel_spacing is not None:
            self._pixel_spacing = SizeMm(*self._tiff_image.pixel_spacing.to_tuple())
        else:
            raise ValueError("Could not determine pixel spacing for tiff image.")
        self._image_coordinate_system = merged_metadata.image_coordinate_system

    @property
    def image_coordinate_system(self) -> ImageCoordinateSystem:
        if self._image_coordinate_system is None:
            return super().image_coordinate_system
        return self._image_coordinate_system

    @property
    def pixel_spacing(self) -> SizeMm:
        return self._pixel_spacing


class OpenTileAssociatedImageData(OpenTileImageData):
    def __init__(
        self,
        tiff_image: TiffImage,
        encoder: Encoder,
        force_transcoding: bool = False,
    ):
        super().__init__(tiff_image, encoder, force_transcoding)
        if self._tiff_image.pixel_spacing is not None:
            self._pixel_spacing = SizeMm(*self._tiff_image.pixel_spacing.to_tuple())
        else:
            self._pixel_spacing = None

    @property
    def pixel_spacing(self) -> Optional[SizeMm]:
        """Size of the pixels in mm/pixel."""
        return self._pixel_spacing
