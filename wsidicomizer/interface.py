import math
import os
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Callable, DefaultDict, Dict, Iterator, List, Tuple, Union

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
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.interface import (ImageData, WsiDataset, WsiDicomGroup,
                                WsiDicomLabels, WsiDicomLevel, WsiDicomLevels,
                                WsiDicomOverviews, WsiDicomSeries, WsiInstance)
from wsidicom.uid import WSI_SOP_CLASS_UID

from .dataset import (create_wsi_dataset, get_image_type)
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


class DicomWsiFileWriter:
    def __init__(self, path: Path) -> None:
        """Return a dicom filepointer.

        Parameters
        ----------
        path: Path
            Path to filepointer.

        """
        self._fp = pydicom.filebase.DicomFile(path, mode='wb')
        self._fp.is_little_endian = True
        self._fp.is_implicit_VR = False

    def write_preamble(self) -> None:
        """Writes file preamble to file."""
        preamble = b'\x00' * 128
        self._fp.write(preamble)
        self._fp.write(b'DICM')

    def write_file_meta(self, uid: Uid, transfer_syntax: Uid) -> None:
        """Writes file meta dataset to file.

        Parameters
        ----------
        uid: Uid
            SOP instance uid to include in file.
        transfer_syntax: Uid
            Transfer syntax used in file.
        """
        meta_ds = pydicom.dataset.FileMetaDataset()
        meta_ds.TransferSyntaxUID = transfer_syntax
        meta_ds.MediaStorageSOPInstanceUID = uid
        meta_ds.MediaStorageSOPClassUID = WSI_SOP_CLASS_UID
        pydicom.dataset.validate_file_meta(meta_ds)
        pydicom.filewriter.write_file_meta_info(self._fp, meta_ds)

    def write_base(self, dataset: WsiDataset) -> None:
        """Writes base dataset to file.

        Parameters
        ----------
        dataset: WsiDataset

        """
        now = datetime.now()
        dataset.ContentDate = datetime.date(now).strftime('%Y%m%d')
        dataset.ContentTime = datetime.time(now).strftime('%H%M%S.%f')
        pydicom.filewriter.write_dataset(self._fp, dataset)

    def write_pixel_data_start(self) -> None:
        """Writes tags starting pixel data."""
        pixel_data_element = pydicom.dataset.DataElement(
            0x7FE00010,
            'OB',
            0,
            is_undefined_length=True
            )

        # Write pixel data tag
        self._fp.write_tag(pixel_data_element.tag)

        if not self._fp.is_implicit_VR:
            # Write pixel data VR (OB), two empty bytes (PS3.5 7.1.2)
            self._fp.write(bytes(pixel_data_element.VR, "iso8859"))
            self._fp.write_US(0)
        # Write unspecific length
        self._fp.write_UL(0xFFFFFFFF)

        # Write item tag and (empty) length for BOT
        self._fp.write_tag(pydicom.tag.ItemTag)
        self._fp.write_UL(0)

    def write_pixel_data(
        self,
        image_data: ImageData,
        z: float,
        path: str
    ) -> None:
        """Writes pixel data to file.

        Parameters
        ----------
        image_data: ImageData
            Image data to read pixel tiles from.
        z: float
            Focal plane to write.
        path: str
            Optical path to write.
        """
        # Single get_tile method
        # tile_points = Region(
        #     Point(0, 0),
        #     image_data.tiled_size
        # ).iterate_all()
        # for tile_point in tile_points:
        #     tile = image_data.get_tile(tile_point, z, path)
        #     for frame in pydicom.encaps.itemize_frame(tile, 1):
        #         fp.write(frame)
        minimum_chunk_size = getattr(
            image_data,
            'suggested_minimum_chunk_size',
            1
        )
        #
        number_of_chunks = 10

        chunk_size = number_of_chunks*minimum_chunk_size

        # Divide the image tiles up into chunk_size chunks (up to tiled size)
        chunked_tile_points = (
            Region(
                Point(x, y),
                Size(min(chunk_size, image_data.tiled_size.width - x), 1)
            ).iterate_all()
            for y in range(image_data.tiled_size.height)
            for x in range(0, image_data.tiled_size.width, chunk_size)
        )
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
            def thread(tile_points: List[Point]) -> List[bytes]:
                # Thread that takes a chunk of tile points and returns list of
                # tile bytes
                return image_data.get_encoded_tiles(tile_points, z, path)

            # Each thread result is a list of tiles that is itemized and writen
            for thread_result in pool.map(thread, chunked_tile_points):
                for tile in thread_result:
                    for frame in pydicom.encaps.itemize_frame(tile, 1):
                        self._fp.write(frame)

    def write_pixel_data_end(self) -> None:
        """Writes tags ending pixel data."""
        self._fp.write_tag(pydicom.tag.SequenceDelimiterTag)
        self._fp.write_UL(0)

    def close(self) -> None:
        self._fp.close()


class WsiDicomGroupSave(WsiDicomGroup):
    """Extend WsiDicomGroup with save-functionality."""
    def _group_instances_to_file(
        self,
    ) -> List[List[WsiInstance]]:
        """Group instances by properties that can't differ in a DICOM-file,
        i.e. the instances are grouped by output file.

        Returns
        ----------
        List[List[WsiInstance]]
            Instances grouped by common properties.
        """
        groups: DefaultDict[Union[str, Uid], List[str]] = DefaultDict(list)
        for instance in self.instances.values():
            groups[
                instance.image_data.photometric_interpretation,
                instance.image_data.transfer_syntax,
                instance.ext_depth_of_field,
                instance.ext_depth_of_field_planes,
                instance.ext_depth_of_field_plane_distance,
                instance.focus_method,
                instance.slice_spacing
            ].append(
                instance
            )
        return list(groups.values())

    @staticmethod
    def _list_image_data(
        instances: List[WsiInstance]
    ) -> Tuple[Tuple[str, float], List[ImageData]]:
        """List and sort ImageData in instances by optical path and focal
        plane.

        Parameters
        ----------
        instances: List[WsiInstance]
            List of instances with optical paths and focal planes to list and
            sort.

        Returns
        ----------
        Tuple[Tuple[str, float], List[ImageData]]
            ImageData listed and sorted by optical path and focal plane.
        """
        output: Dict[Tuple[str, float], ImageData] = {}
        for instance in instances:
            for optical_path in instance.optical_paths:
                for z in instance.focal_planes:
                    if (optical_path, z) not in output:
                        output[optical_path, z] = instance._image_data
        return OrderedDict(output).items()

    def save(
        self,
        output_path: str,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
    ) -> List[Path]:
        """Save a WsiDicomGroup to files in output_path. Instances are grouped
        by properties that can differ in the same file:
            - photometric interpretation
            - transfer syntax
            - extended depth of field (and planes and distance)
            - focus method
            - spacing between slices
        Other properties are assumed to be equal or to be updated.

        Parameters
        ----------
        output_path: str
            Folder path to save files to.

        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
            Uid generator to use.

        Returns
        ----------
        List[str]
            List of paths of created files.
        """
        filepaths: List[Path] = []
        for instances in self._group_instances_to_file():
            uid = uid_generator()
            filepath = os.path.join(output_path, uid + '.dcm')
            transfer_syntax = instances[0]._image_data.transfer_syntax
            dataset = deepcopy(instances[0].dataset)
            wsi_file = DicomWsiFileWriter(filepath)
            wsi_file.write_preamble()
            wsi_file.write_file_meta(uid, transfer_syntax)
            dataset.SOPInstanceUID = uid
            wsi_file.write_base(dataset)
            wsi_file.write_pixel_data_start()
            for (path, z), image_data in self._list_image_data(instances):
                wsi_file.write_pixel_data(image_data, z, path)
            wsi_file.write_pixel_data_end()
            wsi_file.close()
            filepaths.append(filepath)
        return filepaths


class WsiDicomLevelSave(WsiDicomLevel, WsiDicomGroupSave):
    """Extend WsiDicomLevel with save-functionality from WsiDicomGroupSave."""
    pass


class WsiDicomSeriesSave(WsiDicomSeries, metaclass=ABCMeta):
    """Extend WsiDicomSeries with save-functionality."""
    groups: List[WsiDicomGroupSave]

    def save(
        self,
        output_path: str,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
    ) -> List[str]:
        """Save WsiDicomSeries as DICOM-files in path.

        Parameters
        ----------
        output_path: str
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
             Function that can gernerate unique identifiers.

        Returns
        ----------
        List[str]
            List of paths of created files.
        """
        filepaths: List[str] = []
        for group in self.groups:
            group_file_paths = group.save(
                output_path,
                uid_generator
            )
            filepaths.extend(group_file_paths)
        return filepaths


class WsiDicomLabelsSave(WsiDicomLabels, WsiDicomSeriesSave):
    """Extend WsiDicomLabels with save-functionality from WsiDicomSeriesSave.
    """
    group_class = WsiDicomGroupSave


class WsiDicomOverviewsSave(WsiDicomOverviews, WsiDicomSeriesSave):
    """Extend WsiDicomOverviews with save-functionality from
    WsiDicomSeriesSave."""
    group_class = WsiDicomGroupSave


class WsiDicomLevelsSave(WsiDicomLevels, WsiDicomSeriesSave):
    """Extend WsiDicomLevels with save-functionality from WsiDicomSeriesSave.
    """
    group_class = WsiDicomLevelSave


class WsiDicomizer(WsiDicom):
    """WsiDicom class with import tiler-functionality."""
    levels: WsiDicomLevelsSave
    labels: WsiDicomLabelsSave
    overviews: WsiDicomOverviewsSave

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
        levels = WsiDicomLevelsSave.open(level_instances)
        labels = WsiDicomLabelsSave.open(label_instances)
        overviews = WsiDicomOverviewsSave.open(overview_instances)
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
        levels = WsiDicomLevelsSave.open(level_instances)
        labels = WsiDicomLabelsSave.open(label_instances)
        overviews = WsiDicomOverviewsSave.open(overview_instances)
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

    def save(
        self,
        output_path: str,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
    ) -> List[str]:
        """Save wsi as DICOM-files in path.

        Parameters
        ----------
        output_path: str
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
             Function that can gernerate unique identifiers.

        Returns
        ----------
        List[str]
            List of paths of created files.
        """
        collections: List[WsiDicomSeriesSave] = [
            self.levels, self.labels, self.overviews
        ]

        filepaths: List[str] = []
        for collection in collections:
            collection_filepaths = collection.save(
                output_path,
                uid_generator
            )
            filepaths.extend(collection_filepaths)
        return filepaths

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
