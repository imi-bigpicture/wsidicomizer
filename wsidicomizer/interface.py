import os
from pathlib import Path
from typing import Callable, List, Tuple, Union

import pydicom
from opentile.common import Tiler
from opentile.interface import OpenTile
from opentile.turbojpeg_patch import find_turbojpeg_path
from pydicom import config
from pydicom.dataset import Dataset
from pydicom.uid import UID as Uid
from turbojpeg import TurboJPEG
from wsidicom import WsiDicom
from wsidicom.interface import (WsiDataset, WsiDicomLabels, WsiDicomLevels,
                                WsiDicomOverviews, WsiInstance)

from wsidicomizer.dataset import create_wsi_dataset
from wsidicomizer.imagedata_wrapper import ImageDataWrapper
from wsidicomizer.openslide_wrapper import (OpenSlideAssociatedWrapper,
                                            OpenSlideLevelWrapper)
from wsidicomizer.opentile_wrapper import OpenTileWrapper
from openslide import OpenSlide

config.enforce_valid_values = True
config.future_behavior()


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
