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

import math
import os
from abc import ABCMeta
from ctypes import c_uint32
from pathlib import Path
from typing import List, Optional, Sequence, Union

import numpy as np
from PIL import Image
from pydicom import Dataset
from pydicom.uid import UID as Uid
from wsidicom import (WsiDicom, WsiDicomLabels, WsiDicomLevels,
                      WsiDicomOverviews)
from wsidicom.geometry import Point, Size, SizeMm, Region
from wsidicom.wsidicom import WsiDicom
from wsidicom.errors import WsiDicomNotFoundError

from wsidicomizer.common import MetaDicomizer, MetaImageData
from wsidicomizer.dataset import create_base_dataset
from wsidicomizer.encoding import Encoder, create_encoder

if os.name == 'nt':  # On windows, add path to openslide to dll path
    try:
        openslide_dir = os.environ['OPENSLIDE']
    except KeyError:
        raise ValueError(
            "Enviroment variable 'OPENSLIDE'"
            "needs to be set to OpenSlide bin path"
        )
    try:
        os.add_dll_directory(openslide_dir)
    except AttributeError:
        os.environ['PATH'] = (
            openslide_dir + os.pathsep + os.environ['PATH']
        )

from openslide import OpenSlide
from openslide._convert import argb2rgba as convert_argb_to_rgba
from openslide.lowlevel import (ArgumentError, _read_associated_image,
                                _read_region, get_associated_image_dimensions,
                                get_associated_image_names)


class OpenSlideImageData(MetaImageData, metaclass=ABCMeta):
    def __init__(
        self,
        open_slide: OpenSlide,
        encoder: Encoder
    ):
        """Wraps a OpenSlide image to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(encoder)

        self._open_slide = open_slide
        self._background = '#' + open_slide.properties.get(
            'openslide.background-color',
            'ffffff'
        )

    @property
    def files(self) -> List[Path]:
        return [Path(self._open_slide._filename)]

    @property
    def transfer_syntax(self) -> Uid:
        """The uid of the transfer syntax of the image."""
        return self._encoder.transfer_syntax

    def _remove_alpha(self, image_data: np.ndarray) -> np.ndarray:
        """Return image data with applied for white background. Openslide
        returns fully transparent pixels with RGBA-value 0, 0, 0, 0 for
        'sparse' areas. At the edge to 'sparse' areas and at (native) tile
        edges there can also be partial transparency.

        Parameters
        ----------
        image_data: np.ndarray
             Image data in RGBA format.

        Returns
        ----------
        image_data: np.ndarray
             Image data in RGBA format with transparent pixels as white.
        """
        transparency = image_data[:, :, 3]
        image_data[transparency < 254, :] = 255
        return image_data

    def close(self) -> None:
        """Close the open slide object, if not already closed."""
        try:
            self._open_slide.close()
        except ArgumentError:
            # Slide already closed
            pass


class OpenSlideAssociatedImageData(OpenSlideImageData):
    def __init__(
        self,
        open_slide: OpenSlide,
        image_type: str,
        encoder: Encoder
    ):
        """Wraps a OpenSlide associated image (label or overview) to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        image_type: str
            Type of image to wrap.
        encoded: Encoder
            Encoder to use.
        """
        super().__init__(open_slide, encoder)
        self._image_type = image_type
        if image_type not in get_associated_image_names(self._open_slide._osr):
            raise ValueError(f"{image_type} not in {self._open_slide}")

        width, height = get_associated_image_dimensions(
            self._open_slide._osr,
            image_type
        )
        buffer = (width * height * c_uint32)()
        _read_associated_image(self._open_slide._osr, image_type, buffer)
        image_data: np.ndarray = np.frombuffer(buffer, dtype=np.uint8)
        image_data.shape = (width, height, 4)
        image_data = self._remove_alpha(image_data)
        self._encoded_image = self._encode(image_data)
        convert_argb_to_rgba(image_data)
        self._decoded_image = Image.fromarray(image_data).convert('RGB')
        (height, width) = image_data.shape[0:2]
        self._image_size = Size(width, height)

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self.image_size

    @property
    def pixel_spacing(self) -> SizeMm:
        """Size of the pixels in mm/pixel."""
        # TODO figure out pixel spacing for label and overview in openslide.
        return SizeMm(1, 1)

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return 0

    def _get_encoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        if tile != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._encoded_image

    def _get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
        if tile != Point(0, 0):
            raise ValueError("Point(0, 0) only valid tile for non-tiled image")
        return self._decoded_image


class OpenSlideLevelImageData(OpenSlideImageData):
    def __init__(
        self,
        open_slide: OpenSlide,
        level_index: int,
        tile_size: int,
        encoder: Encoder
    ):
        super().__init__(open_slide, encoder)
        """Wraps a OpenSlide level to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        level_index: int
            Level in OpenSlide object to wrap
        tile_size: int
            Output tile size.
        encoded: Encoder
            Encoder to use.
        """
        self._tile_size = Size(tile_size, tile_size)
        self._open_slide = open_slide
        self._level_index = level_index
        self._image_size = Size.from_tuple(
            self._open_slide.level_dimensions[self._level_index]
        )
        self._downsample = int(
            self._open_slide.level_downsamples[self._level_index]
        )
        self._pyramid_index = int(math.log2(self.downsample))

        base_mpp_x = float(self._open_slide.properties['openslide.mpp-x'])
        base_mpp_y = float(self._open_slide.properties['openslide.mpp-y'])
        self._pixel_spacing = SizeMm(
            base_mpp_x * self.downsample / 1000.0,
            base_mpp_y * self.downsample / 1000.0
        )

    @property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return self._image_size

    @property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return self._tile_size

    @property
    def pixel_spacing(self) -> SizeMm:
        """Size of the pixels in mm/pixel."""
        return self._pixel_spacing

    @property
    def downsample(self) -> int:
        """Downsample facator for level."""
        return self._downsample

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return self._pyramid_index

    def stitch_tiles(
        self,
        region: Region,
        path: str,
        z: float
    ) -> Image.Image:
        """Overrides ImageData stitch_tiles() to read reagion directly from
        openslide object.

        Parameters
        ----------
        region: Region
             Pixel region to stitch to image
        path: str
            Optical path
        z: float
            Z coordinate

        Returns
        ----------
        Image.Image
            Stitched image
        """
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'focal plane {z}', str(self))
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'optical path {path}', str(self))
        image_data = self._get_region(region.start, region.size)
        return Image.fromarray(image_data)

    def _get_region(
        self,
        point: Point,
        size: Size
    ) -> np.ndarray:
        if size.width < 0 or size.height < 0:
            raise ValueError('Negative size not allowed')

        location_in_base_level = point * self.downsample
        buffer = (size.width * size.height * c_uint32)()
        _read_region(
            self._open_slide._osr,
            buffer,
            location_in_base_level.x,
            location_in_base_level.y,
            self._level_index,
            size.width,
            size.height
        )
        tile_data: np.ndarray = np.frombuffer(buffer, dtype=np.uint8)
        tile_data.shape = (size.height, size.width, 4)
        tile_data = self._remove_alpha(tile_data)

        return tile_data

    def _get_tile(self, tile_point: Point) -> np.ndarray:
        """Return tile as np array. Transparency is removed.

        Parameters
        ----------
        tile_point: Point
            Tile position to get.

        Returns
        ----------
        Image.Image
            Image of tile.
        """
        return self._get_region(
            tile_point*self.tile_size,
            self.tile_size
        )

    def _get_encoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str
    ) -> bytes:
        """Return image bytes for tile. Transparency is removed and tile is
        encoded as jpeg.

        Parameters
        ----------
        tile_point: Point
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
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'focal plane {z}', str(self))
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'optical path {path}', str(self))
        return self._encode(self._get_tile(tile_point))

    def _get_decoded_tile(
        self,
        tile_point: Point,
        z: float,
        path: str
    ) -> Image.Image:
        """Return Image for tile. Image mode is RGB.

        Parameters
        ----------
        tile_point: Point
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
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'focal plane {z}', str(self))
        if z not in self.focal_planes:
            raise WsiDicomNotFoundError(f'optical path {path}', str(self))
        tile_data = self._get_tile(tile_point)
        tile = Image.fromarray(tile_data)
        return tile


class OpenSlideDicomizer(MetaDicomizer):
    @classmethod
    def open(
        cls,
        filepath: str,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        tile_size: Optional[int] = None,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '422'
    ) -> WsiDicom:
        """Open openslide file in filepath as WsiDicom object. Note that
        created instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to tiff file
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: Optional[int]
            Tile size to use if not defined by file.
        include_levels: Sequence[int] = None
            Levels to include. If None, include all levels.
        include_label: bool = True
            Inclube label.
        include_overview: bool = True
            Include overview.
        include_confidential: bool = True
            Include confidential metadata. Not implemented.
        encoding_format: str = 'jpeg'
            Encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'.
        encoding_quality: int = 90
            Quality to use if re-encoding. Do not use > 95 for jpeg. Use 100
            for lossless jpeg2000.
        jpeg_subsampling: str = '422'
            Subsampling option if using jpeg for re-encoding. Use '444' for
            no subsampling, '422' for 2x2 subsampling.

        Returns
        ----------
        WsiDicom
            WsiDicom object of openslide file in filepath.
        """
        if tile_size is None:
            raise ValueError("Tile size required for open slide")
        encoder = create_encoder(
            encoding_format,
            encoding_quality,
            subsampling=jpeg_subsampling,
            input_colorspace='BGR'
        )
        base_dataset = create_base_dataset(modules)
        slide = OpenSlide(filepath)
        instance_number = 0
        level_instances = [
            cls._create_instance(
                OpenSlideLevelImageData(
                    slide,
                    level_index,
                    tile_size,
                    encoder
                ),
                base_dataset,
                'VOLUME',
                instance_number+level_index
            )
            for level_index in range(slide.level_count)
            if include_levels is None or level_index in include_levels
        ]
        instance_number += len(level_instances)
        if include_label and 'label' in slide.associated_images:
            label_instances = [cls._create_instance(
                OpenSlideAssociatedImageData(slide, 'label', encoder),
                base_dataset,
                'LABEL',
                instance_number
            )]
        else:
            label_instances = []
        instance_number += len(label_instances)
        if include_overview and 'macro' in slide.associated_images:
            overview_instances = [cls._create_instance(
                OpenSlideAssociatedImageData(slide, 'macro', encoder),
                base_dataset,
                'OVERVIEW',
                instance_number
            )]
        else:
            overview_instances = []
        levels = WsiDicomLevels.open(level_instances)
        labels = WsiDicomLabels.open(label_instances)
        overviews = WsiDicomOverviews.open(overview_instances)
        return cls(levels, labels, overviews)

    @staticmethod
    def is_supported(filepath: str) -> bool:
        """Return True if file in filepath is supported by OpenSlide."""
        return OpenSlide.detect_format(str(filepath)) is not None
