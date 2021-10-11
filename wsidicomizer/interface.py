import math
import os
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Callable, Iterator, List, Tuple, Union

import numpy as np
import pydicom
from imagecodecs import jpeg_encode

from opentile.common import OpenTilePage, Tiler
from opentile.interface import OpenTile
from opentile.turbojpeg_patch import find_turbojpeg_path
from PIL import Image
from pydicom import config
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import UID as Uid
from turbojpeg import TJPF_BGRA, TJSAMP_444, TurboJPEG
from wsidicom import WsiDicom
from wsidicom.geometry import Point, Size, SizeMm
from wsidicom.interface import (ImageData, WsiDataset, WsiDicomLabels,
                                WsiDicomLevels, WsiDicomOverviews, WsiInstance)

from .dataset import create_wsi_dataset, get_image_type
from .openslide_patch import OpenSlidePatched as OpenSlide
from openslide._convert import argb2rgba as convert_argb_to_rgba
from openslide.lowlevel import ArgumentError

config.enforce_valid_values = True
config.future_behavior()

# Should be configurable parameters
# Also, it should be possible to configure jpeg2000-compresesion
JPEG_ENCODE_QUALITY = 95
JPEG_ENCODE_SUBSAMPLE = TJSAMP_444


class ImageDataWrapper(ImageData):
    _default_z = 0

    @property
    @abstractmethod
    def pyramid_index(self) -> int:
        raise NotImplementedError

    @property
    def samples_per_pixel(self) -> int:
        return 3

    @property
    def photometric_interpretation(self) -> str:
        # Should be derived from the used subsample format
        return 'YBR_FULL'

    def create_instance_dataset(
        self,
        base_dataset: Dataset,
        image_flavor: str,
        instance_number: int,
        transfer_syntax: Uid,
        photometric_interpretation: str
    ) -> Dataset:
        """Return instance dataset for image_data based on base dataset.

        Parameters
        ----------
        base_dataset: Dataset
            Dataset common for all instances.
        image_flavor:
            Type of instance ('VOLUME', 'LABEL', 'OVERVIEW)

        Returns
        ----------
        Dataset
            Dataset for instance.
        """
        dataset = deepcopy(base_dataset)
        dataset.ImageType = get_image_type(
            image_flavor,
            self.pyramid_index
        )
        dataset.SOPInstanceUID = pydicom.uid.generate_uid(prefix=None)

        shared_functional_group_sequence = Dataset()
        pixel_measure_sequence = Dataset()
        pixel_measure_sequence.PixelSpacing = [
            pydicom.valuerep.DSfloat(self.pixel_spacing.width, True),
            pydicom.valuerep.DSfloat(self.pixel_spacing.height, True)
        ]
        pixel_measure_sequence.SpacingBetweenSlices = 0.0
        pixel_measure_sequence.SliceThickness = 0.0
        shared_functional_group_sequence.PixelMeasuresSequence = (
            DicomSequence([pixel_measure_sequence])
        )
        dataset.SharedFunctionalGroupsSequence = DicomSequence(
            [shared_functional_group_sequence]
        )
        dataset.DimensionOrganizationType = 'TILED_FULL'
        dataset.TotalPixelMatrixColumns = self.image_size.width
        dataset.TotalPixelMatrixRows = self.image_size.height
        dataset.Columns = self.tile_size.width
        dataset.Rows = self.tile_size.height
        dataset.NumberOfFrames = (
            self.tiled_size.width
            * self.tiled_size.height
        )
        dataset.ImagedVolumeWidth = (
            self.image_size.width * self.pixel_spacing.width
        )
        dataset.ImagedVolumeHeight = (
            self.image_size.height * self.pixel_spacing.height
        )
        dataset.ImagedVolumeDepth = 0.0

        if transfer_syntax == pydicom.uid.JPEGBaseline8Bit:
            dataset.BitsAllocated = 8
            dataset.BitsStored = 8
            dataset.HighBit = 7
            dataset.PixelRepresentation = 0
            # dataset.LossyImageCompressionRatio = 1
            dataset.LossyImageCompressionMethod = 'ISO_10918_1'
        if photometric_interpretation == 'YBR_FULL':
            dataset.PhotometricInterpretation = photometric_interpretation
            dataset.SamplesPerPixel = 3

        dataset.PlanarConfiguration = 0

        dataset.InstanceNumber = instance_number
        dataset.FocusMethod = 'AUTO'
        dataset.ExtendedDepthOfField = 'NO'
        return dataset


class OpenSlideWrapper(ImageDataWrapper, metaclass=ABCMeta):
    @property
    def transfer_syntax(self) -> Uid:
        """The uid of the transfer syntax of the image."""
        return pydicom.uid.JPEGBaseline8Bit

    @staticmethod
    def _remove_transparency(image_data: np.ndarray) -> np.ndarray:
        """Removes transparency from image data. Openslide-python produces
        non-premultiplied, 'straigt' RGBA data and the RGB-part can be left
        unmodified. Fully transparent pixels have RGBA-value 0, 0, 0, 0. For
        these, we want full-white pixel instead of full-black.

        Parameters
        ----------
        image_data: np.ndarray
             Image data in RGBA pixel format to remove transparency from.

        Returns
        ----------
        image_data: np.ndarray
            Image data in RGBA pixel format without transparency.
        """
        transparency = image_data[:, :, 3]
        # Check for pixels with full transparency
        image_data[transparency == 0, :] = 255
        return image_data

    def close(self) -> None:
        try:
            self._open_slide.close()
        except ArgumentError:
            # Slide already closed
            pass


class OpenSlideAssociatedWrapper(OpenSlideWrapper):
    def __init__(
        self,
        open_slide: OpenSlide,
        image_type: str,
        jpeg
    ):
        self._image_type = image_type
        self._open_slide = open_slide
        image_data = open_slide.associated_images_np[image_type]
        image_data = self._remove_transparency(image_data)
        self._encoded_image = jpeg.encode(
            image_data,
            JPEG_ENCODE_QUALITY,
            TJPF_BGRA,
            JPEG_ENCODE_SUBSAMPLE
        )
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

    def get_encoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
        if tile != Point(0, 0):
            raise ValueError
        return self._encoded_image

    def get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        if tile != Point(0, 0):
            raise ValueError
        return self._decoded_image


class OpenSlideLevelWrapper(OpenSlideWrapper):
    def __init__(
        self,
        open_slide: OpenSlide,
        level_index: Size,
        tile_size: int,
        jpeg: TurboJPEG
    ):
        """Wraps a OpenSlide level to ImageData.

        Parameters
        ----------
        open_slide: OpenSlide
            OpenSlide object to wrap.
        level_index: int
            Level in OpenSlide object to wrap
        tile_size: Size
            Output tile size.
        jpeg: TurboJPEG
            TurboJPEG object to use.
        """
        self._tile_size = Size(tile_size, tile_size)
        self._open_slide = open_slide
        self._level_index = level_index
        self._jpeg = jpeg
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

    def _get_tile(self, tile: Point, flip: bool = False) -> np.ndarray:
        """Return tile as np array. Transparency is removed. Optionally the
        pixel format can be flipped to RGBA, suitable for opening with PIL.

        Parameters
        ----------
        tile: Point
            Tile position to get.
        flip: bool
            If to flip the pixel format from ARGB to RGBA.

        Returns
        ----------
        np.ndarray
            Numpy array of tile.
        """
        tile_point_in_base_level = tile * self.downsample * self._tile_size
        tile_data = self._open_slide.read_region_np(
                tile_point_in_base_level.to_tuple(),
                self._level_index,
                self._tile_size.to_tuple()
        )
        tile_data = self._remove_transparency(tile_data)
        if flip:
            convert_argb_to_rgba(tile_data)
        return tile_data[:, :, 0:3]

    def get_encoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        """Return image bytes for tile. Transparency is removed and tile is
        encoded as jpeg.

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
            raise ValueError
        return self._jpeg.encode(
            self._get_tile(tile),
            JPEG_ENCODE_QUALITY,
            TJPF_BGRA,
            JPEG_ENCODE_SUBSAMPLE
        )

    def get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
        """Return Image for tile. Image mode is RGBA.

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
        tile = self._get_tile(tile, True)
        return Image.fromarray(tile[:, :, 0:3])


class OpenTileWrapper(ImageDataWrapper):
    def __init__(self, tiled_page: OpenTilePage):
        """Wraps a OpenTilePage to ImageData.

        Parameters
        ----------
        tiled_page: OpenTilePage
            OpenTilePage to wrap.
        """
        self._tiled_page = tiled_page
        self._needs_transcoding = not self.is_supported_transfer_syntax()
        if self.needs_transcoding:
            self._transfer_syntax = pydicom.uid.JPEGBaseline8Bit
        else:
            self._transfer_syntax = self.get_transfer_syntax()
        self._image_size = Size(*self._tiled_page.image_size.to_tuple())
        self._tile_size = Size(*self._tiled_page.tile_size.to_tuple())
        self._tiled_size = Size(*self._tiled_page.tiled_size.to_tuple())
        self._pixel_spacing = SizeMm(
            *self._tiled_page.pixel_spacing.to_tuple()
        )

    def __str__(self) -> str:
        return f"{type(self).__name__} for page {self._tiled_page}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._tiled_page})"

    @property
    def transfer_syntax(self) -> Uid:
        """The uid of the transfer syntax of the image."""
        return self._transfer_syntax

    @property
    def needs_transcoding(self) -> bool:
        """Return true if image data requires transcoding for Dicom
        compatibilty."""
        return self._needs_transcoding

    @property
    def native_compression(self) -> str:
        """Return compression method used in image data."""
        return self._tiled_page.compression

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
    def focal_planes(self) -> List[float]:
        """Focal planes avaiable in the image defined in um."""
        return [self._tiled_page.focal_plane]

    @property
    def optical_paths(self) -> List[str]:
        """Optical paths avaiable in the image."""
        return [self._tiled_page.optical_path]

    @property
    def suggested_minimum_chunk_size(self) -> int:
        """Return suggested minumum chunk size for optimal performance with
        get_encoeded_tiles()."""
        return self._tiled_page.suggested_minimum_chunk_size

    @property
    def pyramid_index(self) -> int:
        """The pyramidal index in relation to the base layer."""
        return self._tiled_page.pyramid_index

    def get_encoded_tile(self, tile: Point, z: float, path: str) -> bytes:
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
            raise ValueError
        if self.needs_transcoding:
            decoded_tile = self._tiled_page.get_decoded_tile(tile.to_tuple())
            return jpeg_encode(decoded_tile)
        return self._tiled_page.get_tile(tile.to_tuple())

    def get_decoded_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> Image.Image:
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
        return Image.fromarray(
            self._tiled_page.get_decoded_tile(tile.to_tuple())
        )

    def get_encoded_tiles(
        self,
        tiles: List[Point],
        z: float,
        path: str
    ) -> Iterator[List[bytes]]:
        """Return list of image bytes for tiles. Returns transcoded tiles if
        non-supported encoding.

        Parameters
        ----------
        tiles: List[Point]
            Tile positions to get.
        z: float
            Focal plane of tile to get.
        path: str
            Optical path of tile to get.

        Returns
        ----------
        Iterator[List[bytes]]
            Iterator of tile bytes.
        """
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        tiles_tuples = (tile.to_tuple() for tile in tiles)
        if not self.needs_transcoding:
            return self._tiled_page.get_tiles(tiles_tuples)
        decoded_tiles = self._tiled_page.get_decoded_tiles(tiles_tuples)
        return [jpeg_encode(tile) for tile in decoded_tiles]

    def close(self) -> None:
        self._tiled_page.close()

    def is_supported_transfer_syntax(self) -> bool:
        """Return true if image data is encoded with Dicom-supported transfer
        syntax."""
        try:
            self.get_transfer_syntax()
            return True
        except NotImplementedError:
            return False

    def get_transfer_syntax(self) -> Uid:
        """Return transfer syntax (Uid) for compression type in image data."""
        compression = self.native_compression
        if compression == 'COMPRESSION.JPEG':
            return pydicom.uid.JPEGBaseline8Bit
        elif compression == 'COMPRESSION.APERIO_JP2000_RGB':
            return pydicom.uid.JPEG2000
        raise NotImplementedError(
            f'Not supported compression {compression}'
        )


class WsiDicomizer(WsiDicom):
    """WsiDicom class with import file-functionality."""

    @classmethod
    def import_tiff(
        cls,
        filepath: str,
        datasets: Union[Dataset, List[Dataset]] = None,
        tile_size: int = None,
        include_levels: List[int] = None,
        include_label: bool = True,
        include_overview: bool = True
    ) -> 'WsiDicomizer':
        """Open data in tiff file as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to tiff file
        datasets: Union[Dataset, List[Dataset]] = None
            Base dataset to use in files. If none, use test dataset.
        tile_size: int
            Tile size to use if not defined by file.
        include_levels: List[int] = None
            Levels to include. If None, include all levels.
        include_label: bool = True
            Inclube label.
        include_overview: bool = True
            Include overview.

        Returns
        ----------
        WsiDicomizer
            WsiDicomizer object of imported tiler.
        """
        base_dataset = cls._create_base_dataset(datasets)
        tiler = OpenTile.open(filepath, tile_size)
        level_instances, label_instances, overview_instances = cls._open_tiler(
            tiler,
            base_dataset,
            include_levels=include_levels,
            include_label=include_label,
            include_overview=include_overview
        )
        levels = WsiDicomLevels.open(level_instances)
        labels = WsiDicomLabels.open(label_instances)
        overviews = WsiDicomOverviews.open(overview_instances)
        return cls(levels, labels, overviews)

    @classmethod
    def import_openslide(
        cls,
        filepath: str,
        tile_size: int,
        datasets: Union[Dataset, List[Dataset]] = None,
        include_levels: List[int] = None,
        include_label: bool = True,
        include_overview: bool = True
    ) -> 'WsiDicomizer':
        """Open data in openslide file as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to tiff file
        tile_size: int
            Tile size to use.
        datasets: Union[Dataset, List[Dataset]] = None
            Base dataset to use in files. If none, use test dataset.
        include_levels: List[int] = None
            Levels to include. If None, include all levels.
        include_label: bool = True
            Inclube label.
        include_overview: bool = True
            Include overview.

        Returns
        ----------
        WsiDicomizer
            WsiDicomizer object of imported openslide file.
        """
        base_dataset = cls._create_base_dataset(datasets)
        slide = OpenSlide(filepath)
        jpeg = TurboJPEG(str(find_turbojpeg_path()))
        instance_number = 0
        level_instances = [
            cls._create_instance(
                OpenSlideLevelWrapper(
                    slide,
                    level_index,
                    tile_size,
                    jpeg
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
                OpenSlideAssociatedWrapper(slide, 'label', jpeg),
                base_dataset,
                'LABEL',
                instance_number
            )]
        else:
            label_instances = []
        instance_number += len(label_instances)
        if include_overview and 'macro' in slide.associated_images:
            overview_instances = [cls._create_instance(
                OpenSlideAssociatedWrapper(slide, 'macro', jpeg),
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

    @classmethod
    def convert(
        cls,
        filepath: str,
        output_path: str = None,
        datasets: Union[Dataset, List[Dataset]] = None,
        tile_size: int = None,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid,
        include_levels: List[int] = None,
        include_label: bool = True,
        include_overview: bool = True
    ) -> None:
        """Convert data in file to DICOM files in output path. Created
        instances get UID from uid_generator. Closes when finished.

        Parameters
        ----------
        filepath: str
            Path to file
        output_path: str = None
            Folder path to save files to.
        datasets: Union[Dataset, List[Dataset]] = None
            Base dataset to use in files. If none, use test dataset.
        tile_size: int
            Tile size to use if not defined by file.
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
             Function that can gernerate unique identifiers.
        include_levels: List[int]
            Optional list of levels to include. Include all levels if None.
        include_label: bool
            Include label(s), default true.
        include_overwiew: bool
            Include overview(s), default true.
        """
        base_dataset = cls._create_base_dataset(datasets)
        if OpenTile.detect_format(filepath) is not None:
            imported_wsi = cls.import_tiff(
                filepath,
                base_dataset,
                tile_size,
                include_levels,
                include_label,
                include_overview
            )
        elif OpenSlide.detect_format(filepath) is not None:
            imported_wsi = cls.import_openslide(
                filepath,
                tile_size,
                base_dataset,
                include_levels=include_levels,
                include_label=include_label,
                include_overview=include_overview
            )
        else:
            raise NotImplementedError(f"Not supported format in {filepath}")

        if output_path is None:
            output_path = str(Path(filepath).parents[0].joinpath(
                Path(filepath).stem
            ))
        try:
            os.mkdir(output_path)
        except FileExistsError:
            ValueError(f'Output path {output_path} already excists')

        imported_wsi.save(output_path, uid_generator)
        imported_wsi.close()

    @staticmethod
    def _create_instance(
        image_data: ImageDataWrapper,
        base_dataset: Dataset,
        image_type: str,
        instance_number: int
    ) -> WsiInstance:
        """Create WsiInstance from OpenTilePage.

        Parameters
        ----------
        image_data: ImageData
            Image data and metadata.
        base_dataset: Dataset
            Base dataset to include.
        image_type: str
            Type of instance to create.
        instance_number: int
            The number of the instance (in a series).

        Returns
        ----------
        WsiInstance
            Created WsiInstance.
        """
        instance_dataset = image_data.create_instance_dataset(
            base_dataset,
            image_type,
            instance_number,
            image_data.transfer_syntax,
            image_data.photometric_interpretation
        )

        return WsiInstance(
            WsiDataset(instance_dataset),
            image_data
        )

    @classmethod
    def _open_tiler(
        cls,
        tiler: Tiler,
        base_dataset: Dataset,
        include_levels: List[int] = None,
        include_label: bool = True,
        include_overview: bool = True
    ) -> Tuple[List[WsiInstance], List[WsiInstance], List[WsiInstance]]:
        """Open tiler to produce WsiInstances.

        Parameters
        ----------
        tiler: Tiler
            Tiler that can produce WsiInstances.
        base_dataset: Dataset
            Base dataset to include in files.
        include_levels: List[int] = None
            Optional list of levels to include. Include all levels if None.
        include_label: bool = True
            Include label(s), default true.
        include_overwiew: bool = True
            Include overview(s), default true.

        Returns
        ----------
        Tuple[List[WsiInstance], List[WsiInstance], List[WsiInstance]]
            Lists of created level, label and overivew instances.
        """
        base_dataset = cls._populate_base_dataset(tiler, base_dataset)
        instance_number = 0
        level_instances = [
            cls._create_instance(
                OpenTileWrapper(level),
                base_dataset,
                'VOLUME',
                instance_number+index
            )
            for index, level in enumerate(tiler.levels)
            if include_levels is None or level.pyramid_index in include_levels
        ]
        instance_number += len(level_instances)
        label_instances = [
            cls._create_instance(
                OpenTileWrapper(label),
                base_dataset,
                'LABEL',
                instance_number+index
            )
            for index, label in enumerate(tiler.labels)
            if include_label
        ]
        instance_number += len(level_instances)
        overview_instances = [
            cls._create_instance(
                OpenTileWrapper(overview),
                base_dataset,
                'OVERVIEW',
                instance_number+index
            )
            for index, overview in enumerate(tiler.overviews)
            if include_overview
        ]

        return level_instances, label_instances, overview_instances

    @staticmethod
    def _create_base_dataset(
        modules: Union[Dataset, List[Dataset]]
    ) -> Dataset:
        """Create a base dataset by combining module datasets with a minimal
        wsi dataset.

        Parameters
        ----------
        modules: Union[Dataset, List[Dataset]]

        Returns
        ----------
        Dataset
            Combined base dataset.
        """
        base_dataset = create_wsi_dataset()
        if isinstance(modules, list):
            for module in modules:
                base_dataset.update(module)
        elif isinstance(modules, Dataset):
            base_dataset.update(modules)
        else:
            raise TypeError(
                'datasets parameter should be singe or list of Datasets'
            )
        return base_dataset

    @staticmethod
    def _populate_base_dataset(
        tiler: Tiler,
        base_dataset: Dataset
    ) -> Dataset:
        """Populate dataset with properties from tiler, if present.
        Parameters
        ----------
        tiler: Tiler
            A opentile Tiler.
        base_dataset: Dataset
            Dataset to append properties to.

        Returns
        ----------
        Dataset
            Dataset with added properties.
        """
        for property, value in tiler.properties.items():
            if property == 'aquisition_datatime':
                base_dataset.AcquisitionDateTime = value
            elif property == 'device_serial_number':
                base_dataset.DeviceSerialNumber = value
            elif property == 'manufacturer':
                base_dataset.Manufacturer = value
            elif property == 'software_versions':
                base_dataset.SoftwareVersions = value
            elif property == 'lossy_image_compression_method':
                base_dataset.LossyImageCompressionMethod = value
            elif property == 'lossy_image_compression_ratio':
                base_dataset.LossyImageCompressionRatio = value
            elif property == 'photometric_interpretation':
                base_dataset.PhotometricInterpretation = value
        return base_dataset
