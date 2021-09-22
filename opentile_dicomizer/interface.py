import copy
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Callable, Iterator, List, Tuple

import pydicom
from highdicom.content import (IssuerOfIdentifier, SpecimenCollection,
                               SpecimenDescription, SpecimenPreparationStep,
                               SpecimenSampling, SpecimenStaining)
from opentile.common import OpenTilePage, Tiler
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import UID as Uid
from wsidicom import WsiDicom
from wsidicom.conceptcode import *
from wsidicom.geometry import Point, Region, Size, SizeMm
from wsidicom.interface import (ImageData, WsiDataset, WsiDicomLabels,
                                WsiDicomLevels, WsiDicomOverviews, WsiInstance)
from wsidicom.uid import WSI_SOP_CLASS_UID


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


def get_image_type(image_flavor: str, level_index: int) -> List[str]:
    """Return image type.

    Parameters
    ----------
    image_flavor: str
        Image flavor ('VOLUME', 'LABEL', 'OVERVIEW')
    level_index: int:
        Pyramidal level index of the image.

    Returns
    ----------
    List[str]
        Image type.
    """
    if image_flavor == 'VOLUME' and level_index == 0:
        resampled = 'NONE'
    else:
        resampled = 'RESAMPLED'

    return ['ORGINAL', 'PRIMARY', image_flavor, resampled]


def append_dataset(dataset_0: Dataset, dataset_1: Dataset) -> Dataset:
    for element in dataset_1.elements():
        dataset_0.add(element)
    return dataset_0


def create_instance_dataset(
    base_dataset: Dataset,
    image_flavor: str,
    tiled_page: OpenTilePage,
    uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
) -> Dataset:
    """Return instance dataset for OpenTilePage based on base dataset.

    Parameters
    ----------
    base_dataset: Dataset
        Dataset common for all instances.
    image_flavor:
        Type of instance ('VOLUME', 'LABEL', 'OVERVIEW)
    tiled_page: OpenTilePage:
        Tiled page with image data and metadata.
    uid_generator: Callable[..., Uid]
        Function that can generate Uids.

    Returns
    ----------
    Dataset
        Dataset for instance.
    """
    dataset = copy.deepcopy(base_dataset)
    dataset.ImageType = get_image_type(
        image_flavor,
        tiled_page.pyramid_index
    )
    dataset.SOPInstanceUID = uid_generator()

    shared_functional_group_sequence = Dataset()
    pixel_measure_sequence = Dataset()
    pixel_measure_sequence.PixelSpacing = [
        tiled_page.pixel_spacing.width,
        tiled_page.pixel_spacing.height
    ]
    pixel_measure_sequence.SpacingBetweenSlices = 0.0
    pixel_measure_sequence.SliceThickness = 0.0
    shared_functional_group_sequence.PixelMeasuresSequence = (
        DicomSequence([pixel_measure_sequence])
    )
    dataset.SharedFunctionalGroupsSequence = DicomSequence(
        [shared_functional_group_sequence]
    )
    dataset.TotalPixelMatrixColumns = tiled_page.image_size.width
    dataset.TotalPixelMatrixRows = tiled_page.image_size.height
    # assert(False)
    dataset.Columns = tiled_page.tile_size.width
    dataset.Rows = tiled_page.tile_size.height
    dataset.ImagedVolumeWidth = (
        tiled_page.image_size.width * tiled_page.pixel_spacing.width
    )
    dataset.ImagedVolumeHeight = (
        tiled_page.image_size.height * tiled_page.pixel_spacing.height
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


def create_minimal_base_dataset(
    uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
) -> Dataset:
    """Return minimal base dataset.

    Parameters
    ----------
    uid_generator: Callable[..., Uid]
        Function that can generate Uids.

    Returns
    ----------
    Dataset
        Minimal WSI dataset.
    """
    dataset = Dataset()
    dataset.StudyInstanceUID = uid_generator()
    dataset.SeriesInstanceUID = uid_generator()
    dataset.FrameOfReferenceUID = uid_generator()
    dataset.Modality = 'SM'
    dataset.SOPClassUID = '1.2.840.10008.5.1.4.1.1.77.1.6'

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
    dataset.SpecimenLabelInImage = 'NO'
    dataset.VolumetricProperties = 'VOLUME'
    return dataset


def create_device_module(
    manufacturer: str = None,
    model_name: str = None,
    serial_number: str = None,
    software_versions: List[str] = None
) -> Dataset:
    dataset = Dataset()
    properties = {
        'Manufacturer': manufacturer,
        'ManufacturerModelName': model_name,
        'DeviceSerialNumber': serial_number,
        'SoftwareVersions': software_versions
    }
    for name, value in properties.items():
        if value is not None:
            setattr(dataset, name, value)
    return dataset


def create_simple_sample(
    sample_id: str,
    embedding_medium: str = None,
    fixative: str = None,
    stainings: List[str] = None,
    uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
) -> Dataset:
    if embedding_medium is not None:
        embedding_medium_code = (
            SpecimenEmbeddingMediaCode(embedding_medium).code
        )
    else:
        embedding_medium_code = None
    if fixative is not None:
        fixative_code = SpecimenFixativesCode(fixative).code
    else:
        fixative_code = None
    if stainings is not None:
        processing_type = SpecimenPreparationProcedureCode('Staining').code
        processing_procedure = SpecimenStaining([
            SpecimenStainsCode(staining).code for staining in stainings
        ])
        sample_preparation_step = SpecimenPreparationStep(
            specimen_id=sample_id,
            processing_type=processing_type,
            processing_procedure=processing_procedure,
            embedding_medium=embedding_medium_code,
            fixative=fixative_code
        )
        sample_preparation_steps = [sample_preparation_step]
    else:
        sample_preparation_steps = None

    specimen = SpecimenDescription(
        specimen_id=sample_id,
        specimen_uid=uid_generator(),
        specimen_preparation_steps=sample_preparation_steps
    )
    return specimen


def create_simple_specimen_module(
    slide_id: str,
    samples: List[Dataset]
) -> Dataset:
    # Generic specimen sequence
    dataset = Dataset()
    dataset.ContainerIdentifier = slide_id

    container_type_code_sequence = Dataset()
    container_type_code_sequence.CodeValue = '258661006'
    container_type_code_sequence.CodingSchemeDesignator = 'SCT'
    container_type_code_sequence.CodeMeaning = 'Slide'
    dataset.ContainerTypeCodeSequence = (
        DicomSequence([container_type_code_sequence])
    )

    container_component_sequence = Dataset()
    container_component_sequence.ContainerComponentMaterial = 'GLASS'
    container_component_type_code_sequence = Dataset()
    container_component_type_code_sequence.CodeValue = '433472003'
    container_component_type_code_sequence.CodingSchemeDesignator = 'SCT'
    container_component_type_code_sequence.CodeMeaning = (
        'Microscope slide coverslip'
    )
    container_component_sequence.ContainerComponentTypeCodeSequence = (
        DicomSequence([container_component_type_code_sequence])
    )
    dataset.ContainerComponentSequence = (
        DicomSequence([container_component_sequence])
    )
    specimen_description_sequence = (
        DicomSequence(samples)
    )
    dataset.SpecimenDescriptionSequence = specimen_description_sequence

    return dataset


def create_generic_optical_path_module() -> Dataset:
    dataset = Dataset()
    # Generic optical path sequence
    optical_path_sequence = Dataset()
    optical_path_sequence.OpticalPathIdentifier = '0'
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

    return dataset


def create_test_base_dataset(
    uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid
) -> Dataset:
    """Return simple base dataset for testing.

    Parameters
    ----------
    uid_generator: Callable[..., Uid]
        Function that can generate Uids.

    Returns
    ----------
    Dataset
        Common dataset.
    """
    dataset = create_minimal_base_dataset(uid_generator)

    # Generic device module
    dataset = append_dataset(dataset, create_device_module(
        'Scanner manufacturer',
        'Scanner model name',
        'Scanner serial number',
        ['Scanner software versions']
    ))

    # Generic specimen module
    dataset = append_dataset(dataset, create_simple_specimen_module(
        'slide id',
        samples=[create_simple_sample(
            'sample id',
            uid_generator=uid_generator
        )]
    ))

    # Generic optical path sequence
    dataset = append_dataset(dataset, create_generic_optical_path_module())

    return dataset


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
        return [self._tiled_page.focal_plane]

    @property
    def optical_paths(self) -> List[str]:
        return [self._tiled_page.optical_path]

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

        chunk_size = 4*10

        # Divide the image tiles up into chunk_size chunks (up to tiled size)
        chunked_tile_points = (
            Region(
                Point(x, y),
                Size(min(chunk_size, self._image_data.tiled_size.width - x), 1)
            ).iterate_all()
            for y in range(self._image_data.tiled_size.height)
            for x in range(0, self._image_data.tiled_size.width, chunk_size)
        )

        with ThreadPoolExecutor(max_workers=4) as pool:
            # Thread that takes a chunk of tile points and returns list of
            # tile bytes
            def thread(tile_points: List[Point]) -> List[bytes]:
                return self._image_data.get_tiles(tile_points)

            # Each thread produces a list of tiles that is itimized and writen
            for thread_job in pool.map(thread, chunked_tile_points):
                for tile in thread_job:
                    for frame in pydicom.encaps.itemize_frame(tile, 1):
                        fp.write(frame)

        # end sequence
        fp.write_tag(pydicom.tag.SequenceDelimiterTag)
        fp.write_UL(0)


class WsiDicomizer(WsiDicom):
    """WsiDicom class with import tiler-functionality."""
    @staticmethod
    def create_instance(
        tiled_page: OpenTilePage,
        base_dataset: Dataset,
        image_type: str,
        uid_generator: Callable[..., Uid],
    ) -> WsiInstanceSave:
        """Create WsiInstanceSave from OpenTilePage.

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
        WsiInstanceSave
            Created WsiInstanceSave.
        """
        instance_dataset = create_instance_dataset(
            base_dataset,
            image_type,
            tiled_page,
            uid_generator
        )

        return WsiInstanceSave(
            WsiDataset(instance_dataset),
            ImageDataWrapper(tiled_page),
            get_transfer_syntax(tiled_page.compression)
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
    def open_tiler(
        cls,
        tiler: Tiler,
        base_dataset: Dataset,
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid,
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
            cls.create_instance(
                level,
                base_dataset,
                'VOLUME',
                uid_generator,
            )
            for level in tiler.levels
            if include_levels is None or level.pyramid_index in include_levels
            and is_supported_transfer_syntax(level.compression)
        ]

        label_instances = [
            cls.create_instance(
                label,
                base_dataset,
                'LABEL',
                uid_generator,
            )
            for label in tiler.labels
            if include_label and
            is_supported_transfer_syntax(label.compression)
        ]
        overview_instances = [
            cls.create_instance(
                overview,
                base_dataset,
                'OVERVIEW',
                uid_generator,
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
        uid_generator: Callable[..., Uid] = pydicom.uid.generate_uid,
        include_levels: List[int] = None,
        include_label: bool = True,
        include_overview: bool = True
    ) -> WsiDicom:
        """Open data in tiler as WsiDicom object.

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
        ) = cls.open_tiler(
            tiler,
            base_dataset,
            uid_generator,
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
        """Convert data in tiler to Dicom files in output path. Closes tiler
        when finished.

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
            uid_generator,
            include_levels,
            include_label,
            include_overview
        )

        for instance in imported_wsi.instances:
            instance.save(output_path)

        tiler.close()
