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

import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

from opentile.common import Tiler
from opentile.interface import OpenTile
from pydicom import config
from pydicom.dataset import Dataset
from pydicom.uid import UID as Uid
from pydicom.uid import generate_uid
from wsidicom import (WsiDataset, WsiDicom, WsiDicomLabels, WsiDicomLevels,
                      WsiDicomOverviews, WsiInstance)

from wsidicomizer.czi_wrapper import CziWrapper
from wsidicomizer.dataset import create_base_dataset, populate_base_dataset
from wsidicomizer.encoding import Encoder, create_encoder
from wsidicomizer.imagedata_wrapper import ImageDataWrapper
from wsidicomizer.openslide_wrapper import (OpenSlide,
                                            OpenSlideAssociatedWrapper,
                                            OpenSlideLevelWrapper)
from wsidicomizer.opentile_wrapper import OpenTileWrapper

config.enforce_valid_values = True
config.future_behavior()


class WsiDicomizer(WsiDicom):
    """WsiDicom class with import file-functionality."""

    @classmethod
    def import_tiff(
        cls,
        filepath: str,
        modules: Optional[Union[Dataset, List[Dataset]]] = None,
        tile_size: Optional[int] = None,
        include_levels: Optional[List[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '422'
    ) -> 'WsiDicomizer':
        """Open data in tiff file as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to tiff file
        modules: Optional[Union[Dataset, List[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: Optional[int]
            Tile size to use if not defined by file.
        include_levels: List[int] = None
            Levels to include. If None, include all levels.
        include_label: bool = True
            Inclube label.
        include_overview: bool = True
            Include overview.
        include_confidential: bool = True
            Include confidential metadata.
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
        WsiDicomizer
            WsiDicomizer object of imported tiler.
        """
        encoder = create_encoder(
            encoding_format,
            encoding_quality,
            subsampling=jpeg_subsampling
        )
        base_dataset = create_base_dataset(modules)
        tiler = OpenTile.open(filepath, tile_size)
        level_instances, label_instances, overview_instances = cls._open_tiler(
            tiler,
            encoder,
            base_dataset,
            include_levels=include_levels,
            include_label=include_label,
            include_overview=include_overview,
            include_confidential=include_confidential
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
        modules: Optional[Union[Dataset, List[Dataset]]] = None,
        include_levels: Optional[List[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '422'
    ) -> 'WsiDicomizer':
        """Open data in openslide file as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to openslide file.
        tile_size: int
            Tile size to use.
        modules: Optional[Union[Dataset, List[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        include_levels: Optional[List[int]] = None
            Levels to include. If None, include all levels.
        include_label: bool = True
            Inclube label.
        include_overview: bool = True
            Include overview.
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
        WsiDicomizer
            WsiDicomizer object of imported openslide file.
        """
        JCS_EXT_BGRA = 9
        encoder = create_encoder(
            encoding_format,
            encoding_quality,
            subsampling=jpeg_subsampling,
            colorspace=JCS_EXT_BGRA
        )
        base_dataset = create_base_dataset(modules)
        slide = OpenSlide(filepath)
        instance_number = 0
        level_instances = [
            cls._create_instance(
                OpenSlideLevelWrapper(slide, level_index, tile_size, encoder),
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
                OpenSlideAssociatedWrapper(slide, 'label', encoder),
                base_dataset,
                'LABEL',
                instance_number
            )]
        else:
            label_instances = []
        instance_number += len(label_instances)
        if include_overview and 'macro' in slide.associated_images:
            overview_instances = [cls._create_instance(
                OpenSlideAssociatedWrapper(slide, 'macro', encoder),
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
    def import_czi(
        cls,
        filepath: str,
        tile_size: int,
        modules: Optional[Union[Dataset, List[Dataset]]] = None,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '422'
    ) -> 'WsiDicomizer':
        """Open data in czi file as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to czi file.
        tile_size: int
            Tile size to use.
        modules: Optional[Union[Dataset, List[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
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
        WsiDicomizer
            WsiDicomizer object of imported czi file.
        """
        encoder = create_encoder(
            encoding_format,
            encoding_quality,
            jpeg_subsampling
        )
        base_dataset = create_base_dataset(modules)
        base_level_instance = cls._create_instance(
            CziWrapper(filepath, tile_size, encoder),
            base_dataset,
            'VOLUME',
            0
        )
        levels = WsiDicomLevels.open([base_level_instance])
        labels = WsiDicomLabels.open([])
        overviews = WsiDicomOverviews.open([])
        return cls(levels, labels, overviews)

    @classmethod
    def convert(
        cls,
        filepath: str,
        output_path: Optional[str] = None,
        modules: Optional[Union[Dataset, List[Dataset]]] = None,
        tile_size: Optional[int] = None,
        uid_generator: Callable[..., Uid] = generate_uid,
        include_levels: Optional[List[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        workers: Optional[int] = None,
        chunk_size: Optional[int] = None,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '422'
    ) -> List[str]:
        """Convert data in file to DICOM files in output path. Created
        instances get UID from uid_generator. Closes when finished.

        Parameters
        ----------
        filepath: str
            Path to file
        output_path: str = None
            Folder path to save files to.
        modules: Optional[Union[Dataset, List[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: int
            Tile size to use if not defined by file.
        uid_generator: Callable[..., Uid] = generate_uid
             Function that can gernerate unique identifiers.
        include_levels: List[int]
            Optional list of levels to include. Include all levels if None.
        include_label: bool
            Include label(s), default true.
        include_overwiew: bool
            Include overview(s), default true.
        include_confidential: bool = True
            Include confidential metadata.
        workers: Optional[int] = None,
            Maximum number of thread workers to use.
        chunk_size: Optional[int] = None,
            Chunk size (number of tiles) to process at a time. Actual chunk
            size also depends on minimun_chunk_size from image_data.
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
        List[str]
            List of paths of created files.
        """
        base_dataset = create_base_dataset(modules)
        if OpenTile.detect_format(Path(filepath)) is not None:
            imported_wsi = cls.import_tiff(
                filepath,
                base_dataset,
                tile_size,
                include_levels=include_levels,
                include_label=include_label,
                include_overview=include_overview,
                include_confidential=include_confidential,
                encoding_format=encoding_format,
                encoding_quality=encoding_quality,
                jpeg_subsampling=jpeg_subsampling
            )
        elif OpenSlide.detect_format(filepath) is not None:
            if tile_size is None:
                raise ValueError("Tile size required for open slide")
            imported_wsi = cls.import_openslide(
                filepath,
                tile_size,
                base_dataset,
                include_levels=include_levels,
                include_label=include_label,
                include_overview=include_overview,
                encoding_format=encoding_format,
                encoding_quality=encoding_quality,
                jpeg_subsampling=jpeg_subsampling
            )
        elif CziWrapper.detect_format(Path(filepath)) is not None:
            if tile_size is None:
                raise ValueError("Tile size required for open slide")
            imported_wsi = cls.import_czi(
                filepath,
                tile_size,
                base_dataset,
                encoding_format=encoding_format,
                encoding_quality=encoding_quality,
                jpeg_subsampling=jpeg_subsampling
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

        created_files = imported_wsi.save(
            output_path,
            uid_generator,
            workers,
            chunk_size
        )
        imported_wsi.close()
        return [str(filepath) for filepath in created_files]

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
        encoder: Encoder,
        base_dataset: Dataset,
        include_levels: Optional[List[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True
    ) -> Tuple[List[WsiInstance], List[WsiInstance], List[WsiInstance]]:
        """Open tiler to produce WsiInstances.

        Parameters
        ----------
        tiler: Tiler
            Tiler that can produce WsiInstances.
        encoder: Encoder
            Encoder to use for re-encoding.
        base_dataset: Dataset
            Base dataset to include in files.
        include_levels: Optional[List[int]] = None
            Optional list of levels to include. Include all levels if None.
        include_label: bool = True
            Include label(s), default true.
        include_overwiew: bool = True
            Include overview(s), default true.
        include_confidential: bool = True
            Include confidential metadata.

        Returns
        ----------
        Tuple[List[WsiInstance], List[WsiInstance], List[WsiInstance]]
            Lists of created level, label and overivew instances.
        """
        base_dataset = populate_base_dataset(
            tiler,
            base_dataset,
            include_confidential
        )
        instance_number = 0
        level_instances = [
            cls._create_instance(
                OpenTileWrapper(level, encoder),
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
                OpenTileWrapper(label, encoder),
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
                OpenTileWrapper(overview, encoder),
                base_dataset,
                'OVERVIEW',
                instance_number+index
            )
            for index, overview in enumerate(tiler.overviews)
            if include_overview
        ]

        return level_instances, label_instances, overview_instances
