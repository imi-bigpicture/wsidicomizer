from pathlib import Path
from typing import Callable, Iterator, List, Tuple
import os
from datetime import datetime

import pydicom
from opentile import TiledPage, Tiler
from pydicom.dataset import Dataset
from pydicom.uid import UID as Uid
from wsidicom import WsiDicom
from wsidicom.geometry import Point, Size, SizeMm, Region
from wsidicom.interface import (ImageData, WsiDataset, WsiDicomLabels,
                                WsiDicomLevels, WsiDicomOverviews, WsiInstance)
from wsidicom.uid import WSI_SOP_CLASS_UID


class ImageDataWrapper(ImageData):
    def __init__(self, tiled_page: TiledPage):
        self._tiled_page = tiled_page

    @property
    def image_size(self) -> Size:
        return self._tiled_page.image_size

    @property
    def tile_size(self) -> Size:
        return self._tiled_page.tile_size

    @property
    def tiled_size(self) -> Size:
        return self._tiled_page.tiled_size

    @property
    def pixel_spacing(self) -> SizeMm:
        return self._tiled_page.pixel_spacing

    @property
    def focal_planes(self) -> List[float]:
        return [0.0]

    @property
    def optical_paths(self) -> List[str]:
        return ['0']

    def get_tile(
        self,
        tile: Point,
        z: float,
        path: str
    ) -> bytes:
        if z not in self.focal_planes or path not in self.optical_paths:
            raise ValueError
        return self._tiled_page.get_tile(tile)

    def get_tiles(self, tiles: List[Point]) -> Iterator[List[bytes]]:
        return self._tiled_page.get_tiles(tiles)

    def close(self) -> None:
        self._tiled_page.close()


class WsiInstanceSave(WsiInstance):
    def save(self, path: Path) -> None:
        """Write instance to file. File is written as TILED_FULL.

        Parameters
        ----------
        path: Path
            Path to directory to write to.
        """

        file_path = os.path.join(path, self.dataset.instance_uid+'.dcm')

        fp = self._create_filepointer(file_path)
        self._write_preamble(fp)
        self._write_file_meta(fp, self.dataset.instance_uid)
        self._write_base(fp, self.dataset)
        self._write_pixel_data(fp)

        # close the file
        fp.close()
        print(f"Wrote file {file_path}")

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

    def _write_file_meta(self, fp: pydicom.filebase.DicomFileLike, uid: Uid):
        """Writes file meta dataset to file.

        Parameters
        ----------
        fp: pydicom.filebase.DicomFileLike
            Filepointer to file to write.
        uid: Uid
            SOP instance uid to include in file.
        """
        meta_ds = pydicom.dataset.FileMetaDataset()
        meta_ds.TransferSyntaxUID = self._transfer_syntax
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
        dataset.DimensionOrganizationType = 'TILED_FULL'
        now = datetime.now()
        dataset.ContentDate = datetime.date(now).strftime('%Y%m%d')
        dataset.ContentTime = datetime.time(now).strftime('%H%M%S.%f')
        dataset.NumberOfFrames = (
            self.tiled_size.width * self.tiled_size.height
        )
        pydicom.filewriter.write_dataset(fp, dataset)

    def _write_pixel_data(
        self,
        fp: pydicom.filebase.DicomFileLike
    ):
        """Writes pixel data to file.

        Parameters
        ----------
        fp: pydicom.filebase.DicomFileLike
            Filepointer to file to write.
        focal_planes: List[float]
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

        tile_geometry = Region(Point(0, 0), self.tiled_size)
        # Generator for the tiles
        tile_jobs = (
            self._image_data.get_tiles(tile_geometry.iterate_all())
        )
        # itemize and and write the tiles
        for tile_job in tile_jobs:
            for tile in tile_job:
                for frame in pydicom.encaps.itemize_frame(tile, 1):
                    fp.write(frame)

        # This method tests faster, but also writes all data at once
        # (takes a lot of memory)
        # fp.write(
        #     self.tiler.get_encapsulated_tiles(tile_geometry.iterate_all())
        # )

        # end sequence
        fp.write_tag(pydicom.tag.SequenceDelimiterTag)
        fp.write_UL(0)


class WsiDicomizer(WsiDicom):
    @staticmethod
    def create_instance(
        tiled_page: TiledPage,
        base_dataset: Dataset,
        image_type: str,
        uid_generator: Callable[..., Uid],
        transfer_syntax: Uid
    ) -> WsiInstance:

        instance_dataset = WsiDataset.create_instance_dataset(
            base_dataset,
            image_type,
            tiled_page.pyramid_index,
            tiled_page.image_size,
            tiled_page.tile_size,
            tiled_page.pixel_spacing,
            uid_generator
        )
        return WsiInstanceSave(
            WsiDataset(instance_dataset),
            ImageDataWrapper(tiled_page),
            transfer_syntax
        )


    @classmethod
    def open_tiler(
        cls,
        tiler: Tiler,
        base_dataset: Dataset,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid,
        transfer_syntax: Uid = pydicom.uid.JPEGBaseline8Bit,
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
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
            Function that can gernerate unique identifiers.
        transfer_syntax: Uid = pydicom.uid.JPEGBaseline8Bit
            Transfer syntax.
        include_levels: List[int] = None
            Optional list of levels to include. Include all levels if None.
        include_label: bool = True
            Include label(s), default true.
        include_overwiew: bool = True
            Include overview(s), default true.
        """
        level_instances = [
            cls.create_instance(
                level,
                base_dataset,
                'VOLUME',
                uid_generator,
                transfer_syntax
            )
            for level in tiler.levels
            if include_levels is None or level.pyramid_index in include_levels
        ]

        label_instances = [
            cls.create_instance(
                label,
                base_dataset,
                'LABEL',
                uid_generator,
                transfer_syntax
            )
            for label in tiler.labels if include_label
        ]
        overview_instances = [
            cls.create_instance(
                overview,
                base_dataset,
                'OVERVIEW',
                uid_generator,
                transfer_syntax
            )
            for overview in tiler.overviews if include_overview
        ]
        return level_instances, label_instances, overview_instances

    @classmethod
    def import_tiler(
        cls,
        tiler: Tiler,
        base_dataset: Dataset = None,
    ) -> 'WsiDicom':
        """Open data in tiler as WsiDicom object.
        Parameters
        ----------
        tiler: Tiler
            Tiler that can produce WsiInstances.
        base_dataset: Dataset
            Base dataset to use in files. If none, use test dataset.
        """
        if base_dataset is None:
            base_dataset = WsiDataset.create_test_base_dataset()

        (
            level_instances,
            label_instances,
            overview_instances
        ) = cls.open_tiler(tiler, base_dataset)
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
        """Convert data in tiler to Dicom files in output path.

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
        level_instances, label_instances, overview_instances = (
            cls.open_tiler(
                tiler,
                base_dataset,
                include_levels=include_levels,
                include_label=include_label,
                include_overview=include_overview
            )
        )

        for instance in level_instances+label_instances+overview_instances:
            instance.save(output_path)

        tiler.close()
