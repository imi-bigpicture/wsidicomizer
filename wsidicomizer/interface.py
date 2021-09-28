import os
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import (Callable, DefaultDict, Dict, Iterator, List,
                    Tuple, Union)

import pydicom
from imagecodecs import jpeg_encode
from opentile.common import OpenTilePage, Tiler
from pydicom.dataset import Dataset
from pydicom.uid import UID as Uid
from wsidicom import WsiDicom
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.interface import (ImageData, WsiDataset, WsiDicomGroup,
                                WsiDicomLabels, WsiDicomLevels,
                                WsiDicomOverviews, WsiInstance)
from wsidicom.uid import WSI_SOP_CLASS_UID

from .dataset import (append_dataset, create_instance_dataset,
                      create_test_base_dataset)


def is_supported_transfer_syntax(compression: str) -> bool:
    try:
        get_transfer_syntax(compression)
        return True
    except NotImplementedError:
        return False


def get_transfer_syntax(compression: str) -> Uid:
    if compression == 'COMPRESSION.JPEG':
        return pydicom.uid.JPEGBaseline8Bit
    elif compression == 'COMPRESSION.APERIO_JP2000_RGB':
        return pydicom.uid.JPEG2000
    raise NotImplementedError(
        f'Not supported compression {compression}'
    )


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
        self._needs_transcoding = not is_supported_transfer_syntax(
            self.native_transfer_syntax
        )

    def __str__(self) -> str:
        return f"{type(self).__name__} for page {self._tiled_page}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._tiled_page})"

    @cached_property
    def transfer_syntax(self) -> Uid:
        """The uid of the transfer syntax of the image."""
        if self.needs_transcoding:
            pydicom.uid.JPEGBaseline8Bit
        return get_transfer_syntax(self._tiled_page.compression)

    @property
    def needs_transcoding(self) -> bool:
        return self._needs_transcoding

    @property
    def native_transfer_syntax(self) -> str:
        return self._tiled_page.compression

    @cached_property
    def image_size(self) -> Size:
        """The pixel size of the image."""
        return Size(*self._tiled_page.image_size.to_tuple())

    @cached_property
    def tile_size(self) -> Size:
        """The pixel tile size of the image."""
        return Size(*self._tiled_page.tile_size.to_tuple())

    @cached_property
    def tiled_size(self) -> Size:
        return Size(*self._tiled_page.tiled_size.to_tuple())

    @cached_property
    def pixel_spacing(self) -> SizeMm:
        """Size of the pixels in mm/pixel."""
        return SizeMm(*self._tiled_page.pixel_spacing.to_tuple())

    @property
    def focal_planes(self) -> List[float]:
        """Focal planes avaiable in the image defined in um."""
        return [self._tiled_page.focal_plane]

    @property
    def optical_paths(self) -> List[str]:
        """Optical paths avaiable in the image."""
        return [self._tiled_page.optical_path]

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
        return [jpeg_encode(tile for tile in decoded_tiles)]

    def close(self) -> None:
        self._tiled_page.close()


class WsiDicomizer(WsiDicom):
    """WsiDicom class with import tiler-functionality."""
    @staticmethod
    def _create_instance(
        tiled_page: OpenTilePage,
        base_dataset: Dataset,
        image_type: str,
    ) -> WsiInstance:
        """Create WsiInstance from OpenTilePage.

        Parameters
        ----------
        tiled_page: OpenTilePage
            OpenTilePage containg image data and metadata.
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
        instance_dataset = create_instance_dataset(
            base_dataset,
            image_type,
            tiled_page
        )

        return WsiInstance(
            WsiDataset(instance_dataset),
            ImageDataWrapper(tiled_page)
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
                level,
                base_dataset,
                'VOLUME',
            )
            for level in tiler.levels
            if include_levels is None or level.pyramid_index in include_levels
            and is_supported_transfer_syntax(level.compression)
        ]

        label_instances = [
            cls._create_instance(
                label,
                base_dataset,
                'LABEL'
            )
            for label in tiler.labels
            if include_label and
            is_supported_transfer_syntax(label.compression)
        ]
        overview_instances = [
            cls._create_instance(
                overview,
                base_dataset,
                'OVERVIEW'
            )
            for overview in tiler.overviews
            if include_overview and
            is_supported_transfer_syntax(overview.compression)
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

        Returns
        ----------
        WsiDicom
            WsiDicom object of imported tiler.
        """
        (
            level_instances,
            label_instances,
            overview_instances
        ) = cls._open_tiler(
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

    @staticmethod
    def _group_instances(
        instances: List[WsiInstance]
    ) -> Dict[Union[str, Uid], List[WsiInstance]]:
        """Group instances by properties that can't differ in a DICOM-file,
        i.e. group instance by file.

        Parameters
        ----------
        instances: List[WsiInstance]
            List of instances to group.

        Returns
        ----------
        Dict[Union[str, Uid], List[WsiInstance]]
            Instances grouped by photometric interpretation and transfer
            syntax.
        """
        groups: DefaultDict[Union[str, Uid], List[str]] = DefaultDict(list)
        for instance in instances:
            groups[
                instance.photometric_interpretation,
                instance._image_data.transfer_syntax
            ].append(
                instance
            )
        return dict(groups)

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

    @staticmethod
    def _create_filepointer(path: Path) -> pydicom.filebase.DicomFile:
        """Return a dicom filepointer.

        Parameters
        ----------
        path: Path
            Path to filepointer.
        Returns
        ----------
        pydicom.filebase.DicomFile
            Created filepointer.
        """
        fp = pydicom.filebase.DicomFile(path, mode='wb')
        fp.is_little_endian = True
        fp.is_implicit_VR = False
        return fp

    @staticmethod
    def _write_preamble(fp: pydicom.filebase.DicomFileLike):
        """Writes file preamble to file.

        Parameters
        ----------
        fp: pydicom.filebase.DicomFileLike
            Filepointer to file to write.
        """
        preamble = b'\x00' * 128
        fp.write(preamble)
        fp.write(b'DICM')

    def _write_file_meta(
        self,
        fp: pydicom.filebase.DicomFileLike,
        uid: Uid,
        transfer_syntax: Uid
    ):
        """Writes file meta dataset to file.

        Parameters
        ----------
        fp: pydicom.filebase.DicomFileLike
            Filepointer to file to write.
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
        pydicom.filewriter.write_file_meta_info(fp, meta_ds)

    def _write_base(
        self,
        fp: pydicom.filebase.DicomFileLike,
        dataset: WsiDataset
    ) -> None:
        """Writes base dataset to file.

        Parameters
        ----------
        fp: pydicom.filebase.DicomFileLike
            Filepointer to file to write.
        dataset: WsiDataset

        """
        now = datetime.now()
        dataset.ContentDate = datetime.date(now).strftime('%Y%m%d')
        dataset.ContentTime = datetime.time(now).strftime('%H%M%S.%f')
        pydicom.filewriter.write_dataset(fp, dataset)

    @staticmethod
    def _write_pixel_data_start(
        fp: pydicom.filebase.DicomFileLike
    ) -> None:
        """Writes tags starting pixel data.

        Parameters
        ----------
        fp: pydicom.filebase.DicomFileLike
            Filepointer to file to write.
        """
        pixel_data_element = pydicom.dataset.DataElement(
            0x7FE00010,
            'OB',
            0,
            is_undefined_length=True
            )

        # Write pixel data tag
        fp.write_tag(pixel_data_element.tag)

        if not fp.is_implicit_VR:
            # Write pixel data VR (OB), two empty bytes (PS3.5 7.1.2)
            fp.write(bytes(pixel_data_element.VR, "iso8859"))
            fp.write_US(0)
        # Write unspecific length
        fp.write_UL(0xFFFFFFFF)

        # Write item tag and (empty) length for BOT
        fp.write_tag(pydicom.tag.ItemTag)
        fp.write_UL(0)

    @staticmethod
    def _write_pixel_data(
        fp: pydicom.filebase.DicomFileLike,
        image_data: ImageData,
        z: float,
        path: str
    ):
        """Writes pixel data to file.

        Parameters
        ----------
        fp: pydicom.filebase.DicomFileLike
            Filepointer to file to write.
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

        chunk_size = 4*10

        # Divide the image tiles up into chunk_size chunks (up to tiled size)
        chunked_tile_points = (
            Region(
                Point(x, y),
                Size(min(chunk_size, image_data.tiled_size.width - x), 1)
            ).iterate_all()
            for y in range(image_data.tiled_size.height)
            for x in range(0, image_data.tiled_size.width, chunk_size)
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            # Thread that takes a chunk of tile points and returns list of
            # tile bytes
            def thread(tile_points: List[Point]) -> List[bytes]:
                return image_data.get_tiles(tile_points, z, path)

            # Each thread produces a list of tiles that is itimized and writen
            for thread_job in pool.map(thread, chunked_tile_points):
                for tile in thread_job:
                    for frame in pydicom.encaps.itemize_frame(tile, 1):
                        fp.write(frame)

    @staticmethod
    def _write_pixel_data_end(
        fp: pydicom.filebase.DicomFileLike,
    ) -> None:
        """Writes tags ending pixel data.

        Parameters
        ----------
        fp: pydicom.filebase.DicomFileLike
            Filepointer to file to write.
        """
        # end sequence
        fp.write_tag(pydicom.tag.SequenceDelimiterTag)
        fp.write_UL(0)

    def _save_group(
        self,
        output_path: Path,
        base_dataset: Dataset,
        group: WsiDicomGroup,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
    ) -> None:
        """Save a WsiDicomGroup to files in output_path. Instances are grouped
        by properties that can differ in the same file:
            - photometric interpretation
            - transfer syntax
            - (not yet) extended depth of field (and planes and distance)
            - (not yet) focus method
            - (not yet) spacing between slices

        Parameters
        ----------
        output_path: Path
            Folder path to save files to.
        base_dataset: Dataset
            Dataset to use as base for each file.
        group: WsiDicomGroup
            Group (level, label, or overview) to save.
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
            Uid generator to use.
        """
        # We should group on properties that cant differ in the same file:
        # photometric interpretation
        # transfer syntax
        # focus/focal plane thingies
        for (photometric_interpretation, transfer_syntax), instances in (
            self._group_instances(group.instances.values()).items()
        ):
            # Uid to use for file name and as instance uid
            uid = uid_generator()
            file_path = os.path.join(output_path, uid + '.dcm')

            fp = self._create_filepointer(file_path)
            self._write_preamble(fp)
            self._write_file_meta(fp, uid, transfer_syntax)
            dataset = append_dataset(base_dataset, instances[0].dataset)
            dataset.SOPInstanceUID = uid
            self._write_base(fp, dataset)
            self._write_pixel_data_start(fp)
            for (path, z), image_data in self._list_image_data(instances):
                self._write_pixel_data(fp, image_data, z, path)

            self._write_pixel_data_end(fp)
            fp.close()
            print(f"Wrote file {file_path}")

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
        for collection in [self.levels, self.labels, self.overviews]:
            for group in collection:
                self._save_group(
                    output_path,
                    base_dataset,
                    group,
                    uid_generator
                )



