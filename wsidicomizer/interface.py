import os
from abc import ABCMeta
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Callable, DefaultDict, Dict, Iterator, List, Tuple, Union

import pydicom
from imagecodecs import jpeg_encode
from opentile.common import OpenTilePage, Tiler
from pydicom.dataset import Dataset
from pydicom.filebase import DicomFile
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import UID as Uid
from wsidicom import WsiDicom
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.interface import (ImageData, WsiDataset, WsiDicomGroup,
                                WsiDicomLabels, WsiDicomLevel, WsiDicomLevels,
                                WsiDicomOverviews, WsiDicomSeries, WsiInstance)
from wsidicom.uid import WSI_SOP_CLASS_UID

from .dataset import append_dataset, create_test_base_dataset, get_image_type


class ImageDataWrapper(ImageData):
    def __init__(self, tiled_page: OpenTilePage):
        """Wraps a OpenTilePage to ImageData. Get tile is wrapped by removing
        focal and optical path parameters. Image geometry properties are
        converted to wsidicom.geometry class.

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
    def tiled_size(self) -> Size:
        """The size of the image when divided into tiles, e.g. number of
        columns and rows of tiles. Equals (1, 1) if image is not tiled."""
        return self._tiled_size

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
        get_tiles()."""
        return self._tiled_page.suggested_minimum_chunk_size

    def get_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        if not self.needs_transcoding:
            return self._tiled_page.get_tile(tile.to_tuple())
        decoded_tile = self._tiled_page.get_decoded_tile(tile.to_tuple())
        return jpeg_encode(decoded_tile)

    def get_tiles(
        self,
        tiles: List[Point],
        z: float,
        path: str
    ) -> Iterator[List[bytes]]:
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

    def create_instance_dataset(
        self,
        base_dataset: Dataset,
        image_flavor: str
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
            self._tiled_page.pyramid_index
        )
        dataset.SOPInstanceUID = pydicom.uid.generate_uid(prefix=None)

        shared_functional_group_sequence = Dataset()
        pixel_measure_sequence = Dataset()
        pixel_measure_sequence.PixelSpacing = [
            self.pixel_spacing.width,
            self.pixel_spacing.height
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
        # If PhotometricInterpretation is YBR and no subsampling
        dataset.SamplesPerPixel = 3
        dataset.PhotometricInterpretation = 'YBR_FULL'
        # If transfer syntax pydicom.uid.JPEGBaseline8Bit
        dataset.BitsAllocated = 8
        dataset.BitsStored = 8
        dataset.HighBit = 7
        dataset.PixelRepresentation = 0
        dataset.LossyImageCompression = '01'
        # dataset.LossyImageCompressionRatio = 1
        # dataset.LossyImageCompressionMethod = 'ISO_10918_1'

        # Should be incremented
        dataset.InstanceNumber = 0
        dataset.FocusMethod = 'AUTO'
        dataset.ExtendedDepthOfField = 'NO'
        return dataset


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
        chunk_size = 10*minimum_chunk_size

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
            # Thread that takes a chunk of tile points and returns list of
            # tile bytes
            def thread(tile_points: List[Point]) -> List[bytes]:
                return image_data.get_tiles(tile_points, z, path)

            # Each thread produces a list of tiles that is itimized and writen
            for thread_job in pool.map(thread, chunked_tile_points):
                for tile in thread_job:
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
                instance.photometric_interpretation,
                instance._image_data.transfer_syntax,
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
        output_path: Path,
        base_dataset: Dataset,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
    ) -> None:
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
        output_path: Path
            Folder path to save files to.
        base_dataset: Dataset
            Dataset to use as base for each file.
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
            Uid generator to use.
        """
        for instances in self._group_instances_to_file():
            uid = uid_generator()
            file_path = os.path.join(output_path, uid + '.dcm')
            transfer_syntax = instances[0]._image_data.transfer_syntax
            dataset = deepcopy(instances[0].dataset)
            wsi_file = DicomWsiFileWriter(file_path)
            wsi_file.write_preamble()
            wsi_file.write_file_meta(uid, transfer_syntax)
            dataset = append_dataset(dataset, base_dataset)
            dataset.SOPInstanceUID = uid
            wsi_file.write_base(dataset)
            wsi_file.write_pixel_data_start()
            for (path, z), image_data in self._list_image_data(instances):
                wsi_file.write_pixel_data(image_data, z, path)
            wsi_file.write_pixel_data_end()
            wsi_file.close()
            print(f"Wrote file {file_path}")


class WsiDicomLevelSave(WsiDicomLevel, WsiDicomGroupSave):
    """Extend WsiDicomLevel with save-functionality from WsiDicomGroupSave."""
    pass


class WsiDicomSeriesSave(WsiDicomSeries, metaclass=ABCMeta):
    """Extend WsiDicomSeries with save-functionality."""
    groups: List[WsiDicomGroupSave]

    def save(
        self,
        output_path: Path,
        base_dataset: Dataset,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
    ) -> None:
        """Save WsiDicomSeries as DICOM-files in path.

        Parameters
        ----------
        output_path: Path
        base_dataset: Dataset
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
             Function that can gernerate unique identifiers.
        """
        for group in self.groups:
            group.save(
                output_path,
                base_dataset,
                uid_generator
            )


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

    @staticmethod
    def _create_instance(
        image_data: ImageData,
        base_dataset: Dataset,
        image_type: str
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
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
            Function that can gernerate unique identifiers.

        Returns
        ----------
        WsiInstance
            Created WsiInstance.
        """
        instance_dataset = image_data.create_instance_dataset(
            base_dataset,
            image_type
        )

        return WsiInstance(
            WsiDataset(instance_dataset),
            image_data
        )

    @staticmethod
    def populate_base_dataset(
        tiler: Tiler,
        base_dataset: Dataset
    ) -> Dataset:
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
        base_dataset = cls.populate_base_dataset(tiler, base_dataset)
        level_instances = [
            cls._create_instance(
                ImageDataWrapper(level),
                base_dataset,
                'VOLUME'
            )
            for level in tiler.levels
            if include_levels is None or level.pyramid_index in include_levels
        ]

        label_instances = [
            cls._create_instance(
                ImageDataWrapper(label),
                base_dataset,
                'LABEL'
            )
            for label in tiler.labels
            if include_label
        ]
        overview_instances = [
            cls._create_instance(
                ImageDataWrapper(overview),
                base_dataset,
                'OVERVIEW'
            )
            for overview in tiler.overviews
            if include_overview
        ]

        return level_instances, label_instances, overview_instances

    @classmethod
    def import_tiler(
        cls,
        tiler: Tiler,
        base_dataset: Dataset = create_test_base_dataset(),
        include_levels: List[int] = None,
        include_label: bool = True,
        include_overview: bool = True
    ) -> 'WsiDicomizer':
        """Open data in tiler as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        tiler: Tiler
            Tiler that can produce WsiInstances.
        base_dataset: Dataset
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
            WsiDicomizer object of imported tiler.
        """
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
    def convert(
        cls,
        output_path: Path,
        tiler: Tiler,
        base_dataset: Dataset,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid,
        include_levels: List[int] = None,
        include_label: bool = True,
        include_overview: bool = True
    ) -> None:
        """Convert data in tiler to DICOM files in output path. Created
        instances get UID from uid_generator. Closes tiler when finished.

        Parameters
        ----------
        output_path: Path
            Folder path to save files to.
        tiler: Tiler
            Tiler that can produce WsiInstances.
        base_dataset: Dataset
            Base dataset to include in files.
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
             Function that can gernerate unique identifiers.
        include_levels: List[int]
            Optional list of levels to include. Include all levels if None.
        include_label: bool
            Include label(s), default true.
        include_overwiew: bool
            Include overview(s), default true.
        """
        imported_wsi = cls.import_tiler(
            tiler,
            base_dataset,
            include_levels,
            include_label,
            include_overview
        )
        imported_wsi.save(output_path, base_dataset, uid_generator)
        tiler.close()

    def save(
        self,
        output_path: Path,
        base_dataset: Dataset,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
    ) -> None:
        """Save wsi as DICOM-files in path.

        Parameters
        ----------
        output_path: Path
        base_dataset: Dataset
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
             Function that can gernerate unique identifiers.
        """
        collections: List[WsiDicomSeriesSave] = [
            self.levels, self.labels, self.overviews
        ]
        for collection in collections:
            collection.save(
                output_path,
                base_dataset,
                uid_generator
            )
