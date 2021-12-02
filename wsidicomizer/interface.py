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
from typing import Callable, List, Optional, Sequence, Type, Union

from pydicom.dataset import Dataset
from pydicom.uid import UID, generate_uid
from wsidicom import WsiDicom

from wsidicomizer.common import MetaDicomizer
from wsidicomizer.czi import CziDicomizer
from wsidicomizer.openslide import OpenSlideDicomizer
from wsidicomizer.opentile import OpenTileDicomizer

# List of supported Dicomizers in prioritization order.
SUPPORTED_TILE_SOURCES: List[Type[MetaDicomizer]] = [
    OpenTileDicomizer,
    CziDicomizer,
    OpenSlideDicomizer
]


class WsiDicomizer:
    """Interface for Dicomizing files."""
    @staticmethod
    def open(
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
        """Open data in file in filepath as WsiDicom.

        Parameters
        ----------
        filepath: str
            Path to file
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: int
            Tile size to use if not defined by file.
        include_levels: Sequence[int]
            Optional list of levels to include. Include all levels if None.
        include_label: bool
            Include label(s), default true.
        include_overwiew: bool
            Include overview(s), default true.
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
        WsiDicom
            WsiDicom object of file.
        """
        selected_tile_source = next(
            (
                tile_source for tile_source in SUPPORTED_TILE_SOURCES
                if tile_source.is_supported(filepath)
            ),
            None
        )
        if selected_tile_source is None:
            raise NotImplementedError(f"{filepath} is not supported")

        return selected_tile_source.open(
            filepath,
            modules,
            tile_size,
            include_levels,
            include_label,
            include_overview,
            include_confidential,
            encoding_format,
            encoding_quality,
            jpeg_subsampling
        )

    @classmethod
    def convert(
        cls,
        filepath: str,
        output_path: Optional[str] = None,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        tile_size: Optional[int] = None,
        uid_generator: Callable[..., UID] = generate_uid,
        include_levels: Optional[Sequence[int]] = None,
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
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: int
            Tile size to use if not defined by file.
        uid_generator: Callable[..., UID] = generate_uid
             Function that can gernerate unique identifiers.
        include_levels: Sequence[int]
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
        with cls.open(
            filepath,
            modules,
            tile_size,
            include_levels,
            include_label,
            include_overview,
            include_confidential,
            encoding_format,
            encoding_quality,
            jpeg_subsampling
        ) as wsi:
            if output_path is None:
                output_path = str(Path(filepath).parents[0].joinpath(
                    Path(filepath).stem
                ))
            try:
                os.mkdir(output_path)
            except FileExistsError:
                ValueError(f'Output path {output_path} already excists')
            created_files = wsi.save(
                output_path,
                uid_generator,
                workers,
                chunk_size
            )

        return [str(filepath) for filepath in created_files]
