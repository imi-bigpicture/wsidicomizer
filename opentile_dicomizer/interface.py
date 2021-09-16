import copy
import os
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Callable, Iterator, List, Tuple

import pydicom
from opentile import TiledPage, Tiler
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import UID as Uid
from wsidicom import WsiDicom
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.interface import (ImageData, WsiDataset, WsiDicomLabels,
                                WsiDicomLevels, WsiDicomOverviews, WsiInstance)
from wsidicom.uid import WSI_SOP_CLASS_UID


def get_image_type(image_flavor: str, level_index: int) -> List[str]:
    if image_flavor == 'VOLUME' and level_index == 0:
        resampled = 'NONE'
    else:
        resampled = 'RESAMPLED'

    return ['ORGINAL', 'PRIMARY', image_flavor, resampled]


def create_instance_dataset(
    base_dataset: Dataset,
    image_flavour: str,
    level_index: int,
    image_size: Size,
    tile_size: Size,
    mpp: SizeMm,
    uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
) -> Dataset:
    dataset = copy.deepcopy(base_dataset)
    dataset.ImageType = get_image_type(image_flavour, level_index)
    dataset.SOPInstanceUID = uid_generator()

    shared_functional_group_sequence = Dataset()
    pixel_measure_sequence = Dataset()
    pixel_measure_sequence.PixelSpacing = [mpp.width, mpp.height]
    pixel_measure_sequence.SpacingBetweenSlices = 0.0
    pixel_measure_sequence.SliceThickness = 0.0
    shared_functional_group_sequence.PixelMeasuresSequence = (
        DicomSequence([pixel_measure_sequence])
    )
    dataset.SharedFunctionalGroupsSequence = DicomSequence(
        [shared_functional_group_sequence]
    )
    dataset.TotalPixelMatrixColumns = image_size.width
    dataset.TotalPixelMatrixRows = image_size.height
    dataset.Columns = tile_size.width
    dataset.Rows = tile_size.height
    dataset.ImagedVolumeWidth = image_size.width * mpp.width
    dataset.ImagedVolumeHeight = image_size.height * mpp.height
    dataset.ImagedVolumeDepth = 0.0
    # If PhotometricInterpretation is YBR and no subsampling
    dataset.SamplesPerPixel = 3
    dataset.PhotometricInterpretation = 'YBR_FULL'
    # If transfer syntax pydicom.uid.JPEGBaseline8Bit
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 8
    dataset.PixelRepresentation = 0
    dataset.LossyImageCompression = '01'
    dataset.LossyImageCompressionRatio = 1
    dataset.LossyImageCompressionMethod = 'ISO_10918_1'

    # Should be incremented
    dataset.InstanceNumber = 0
    dataset.FocusMethod = 'AUTO'
    dataset.ExtendedDepthOfField = 'NO'
    return dataset

def create_test_base_dataset(
    uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
) -> Dataset:
    dataset = Dataset()
    dataset.StudyInstanceUID = uid_generator()
    dataset.SeriesInstanceUID = uid_generator()
    dataset.FrameOfReferenceUID = uid_generator()
    dataset.Modality = 'SM'
    dataset.SOPClassUID = '1.2.840.10008.5.1.4.1.1.77.1.6'
    dataset.Manufacturer = 'Manufacturer'
    dataset.ManufacturerModelName = 'ManufacturerModelName'
    dataset.DeviceSerialNumber = 'DeviceSerialNumber'
    dataset.SoftwareVersions = ['SoftwareVersions']

    # Generic specimen sequence
    dataset.ContainerIdentifier = 'ContainerIdentifier'
    specimen_description_sequence = Dataset()
    specimen_description_sequence.SpecimenIdentifier = 'SpecimenIdentifier'
    specimen_description_sequence.SpecimenUID = uid_generator()
    dataset.SpecimenDescriptionSequence = DicomSequence(
        [specimen_description_sequence]
    )

    # Generic optical path sequence
    optical_path_sequence = Dataset()
    optical_path_sequence.OpticalPathIdentifier = '1'
    illumination_type_code_sequence = Dataset()
    illumination_type_code_sequence.CodeValue = '111744'
    illumination_type_code_sequence.CodingSchemeDesignator = 'DCM'
    illumination_type_code_sequence.CodeMeaning = (
        'Brightfield illumination'
    )
    optical_path_sequence.IlluminationTypeCodeSequence = DicomSequence(
        [illumination_type_code_sequence]
    )
    illumination_color_code_sequence = Dataset()
    illumination_color_code_sequence.CodeValue = 'R-102C0'
    illumination_color_code_sequence.CodingSchemeDesignator = 'SRT'
    illumination_color_code_sequence.CodeMeaning = 'Full Spectrum'
    optical_path_sequence.IlluminationColorCodeSequence = DicomSequence(
        [illumination_color_code_sequence]
    )
    dataset.OpticalPathSequence = DicomSequence([optical_path_sequence])

    # Generic dimension organization sequence
    dimension_organization_uid = uid_generator()
    dimension_organization_sequence = Dataset()
    dimension_organization_sequence.DimensionOrganizationUID = (
        dimension_organization_uid
    )
    dataset.DimensionOrganizationSequence = DicomSequence(
        [dimension_organization_sequence]
    )

    # Generic dimension index sequence
    dimension_index_sequence = Dataset()
    dimension_index_sequence.DimensionOrganizationUID = (
        dimension_organization_uid
    )
    dimension_index_sequence.DimensionIndexPointer = (
        pydicom.tag.Tag('PlanePositionSlideSequence')
    )
    dataset.DimensionIndexSequence = DicomSequence(
        [dimension_index_sequence]
    )

    dataset.BurnedInAnnotation = 'NO'
    dataset.BurnedInAnnotation = 'NO'
    dataset.SpecimenLabelInImage = 'NO'
    dataset.VolumetricProperties = 'VOLUME'
    return dataset


class ImageDataWrapper(ImageData):
    """Wraps a TiledPage to ImageData. Get tile is wrapped by removing
    focal and optical path parameters. Image geometry properties are converted
    to wsidicom.geometry class."""
    def __init__(self, tiled_page: TiledPage):
        self._tiled_page = tiled_page

    @cached_property
    def image_size(self) -> Size:
        return Size(*self._tiled_page.image_size.to_tuple())

    @cached_property
    def tile_size(self) -> Size:
        return Size(*self._tiled_page.tile_size.to_tuple())

    @cached_property
    def tiled_size(self) -> Size:
        return Size(*self._tiled_page.tiled_size.to_tuple())

    @cached_property
    def pixel_spacing(self) -> SizeMm:
        return SizeMm(*self._tiled_page.pixel_spacing.to_tuple())

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
        return self._tiled_page.get_tile(tile.to_tuple())

    def get_tiles(self, tiles: List[Point]) -> Iterator[List[bytes]]:
        tiles_ = (tile.to_tuple() for tile in tiles)
        return self._tiled_page.get_tiles(tiles_)

    def close(self) -> None:
        self._tiled_page.close()


class WsiInstanceSave(WsiInstance):
    """WsiInstance with save to file functionality."""
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
    """WsiDicom class with import tiler-functionality."""
    @staticmethod
    def create_instance(
        tiled_page: TiledPage,
        base_dataset: Dataset,
        image_type: str,
        uid_generator: Callable[..., Uid],
        transfer_syntax: Uid
    ) -> WsiInstance:

        instance_dataset = create_instance_dataset(
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
                uid_generator,
                include_levels=include_levels,
                include_label=include_label,
                include_overview=include_overview
            )
        )

        for instance in level_instances+label_instances+overview_instances:
            instance.save(output_path)

        tiler.close()
