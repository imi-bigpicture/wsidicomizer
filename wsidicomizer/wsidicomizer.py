#    Copyright 2021, 2022, 2023 SECTRA AB
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

"""
Main module containing the WsiDicomizer class that allows non-DICOM files to be opened
like DICOM instances, enabling viewing and saving.
"""

import os
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Type, Union

from PIL.Image import Image as PILImage
from pydicom.uid import UID, generate_uid
from wsidicom import WsiDicom

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.encoding import Encoder
from wsidicomizer.sources import CziSource, OpenTileSource, TiffSlideSource
from wsidicomizer.metadata.wsi import WsiMetadata

# List of supported Dicomizers in prioritization order.
loaded_sources: List[Type[DicomizerSource]] = [
    OpenTileSource,
    TiffSlideSource,
    CziSource,
]

try:
    from wsidicomizer.extras.openslide import OpenSlideSource

    loaded_sources.append(OpenSlideSource)
except ImportError:
    pass


class WsiDicomizer(WsiDicom):
    """Interface for Dicomizing files."""

    @classmethod
    def open(
        cls,
        filepath: Union[str, Path],
        metadata: Optional[WsiMetadata] = None,
        tile_size: int = 512,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        encoding_format: str = "jpeg",
        encoding_quality: float = 90,
        jpeg_subsampling: str = "420",
        label: Optional[Union[PILImage, str, Path]] = None,
        preferred_source: Optional[Type[DicomizerSource]] = None,
        **source_args,
    ) -> WsiDicom:
        """Open data in file in filepath as WsiDicom.

        Parameters
        ----------
        filepath: str
            Path to file
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: int = 512
            Tile size to use if not defined by file.
        include_levels: Optional[Sequence[int]] = None
            Optional list indices (in present levels) to include, e.g. [0, 1]
            includes the two lowest levels. Negative indices can be used,
            e.g. [-1, -2] includes the two highest levels.
        include_label: bool = True
            Include label(s), default true.
        include_overwiew: bool = True
            Include overview(s), default true.
        include_confidential: bool = True
            Include confidential metadata.
        encoding_format: str = 'jpeg'
            Encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'.
        encoding_quality: float = 90
            Quality to use if re-encoding. It is recommended to not use > 95 for jpeg.
            Use < 1 or > 1000 for lossless jpeg2000.
        jpeg_subsampling: str = '420'
            Subsampling option if using jpeg for re-encoding. Use '444' for
            no subsampling, '422' for 2x1 subsampling, and '420' for 2x2
            subsampling.
        label: Optional[Union[PILImage, str, Path]] = None
            Optional label image to use instead of label found in file.
        preferred_source: Optional[Type[DicomizerSource]] = None
            Optional override source to use.
        **source_args
            Optional keyword args to pass to source.

        Returns
        ----------
        WsiDicom
            WsiDicom object of file.
        """
        if not isinstance(filepath, Path):
            filepath = Path(filepath)

        selected_source = None
        if preferred_source is None:
            selected_source = next(
                (source for source in loaded_sources if source.is_supported(filepath)),
                None,
            )
        elif preferred_source.is_supported(filepath):
            selected_source = preferred_source
        if selected_source is None:
            raise NotImplementedError(f"{filepath} is not supported")
        encoder = Encoder.create_encoder(
            encoding_format, encoding_quality, subsampling=jpeg_subsampling
        )

        source = selected_source(
            filepath,
            encoder,
            tile_size,
            metadata,
            include_levels,
            include_label,
            include_overview,
            include_confidential,
            **source_args,
        )
        return cls(source, label)

    @classmethod
    def convert(
        cls,
        filepath: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        metadata: Optional[WsiMetadata] = None,
        tile_size: int = 512,
        uid_generator: Callable[..., UID] = generate_uid,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        workers: Optional[int] = None,
        chunk_size: Optional[int] = None,
        encoding_format: str = "jpeg",
        encoding_quality: float = 90,
        jpeg_subsampling: str = "420",
        offset_table: Optional[str] = "bot",
        label: Optional[Union[PILImage, str, Path]] = None,
        preferred_source: Optional[Type[DicomizerSource]] = None,
        **source_args,
    ) -> List[str]:
        """Convert data in file to DICOM files in output path. Created
        instances get UID from uid_generator. Closes when finished.

        Parameters
        ----------
        filepath: Union[str, Path],
            Path to file
        output_path: str = None
            Folder path to save files to.
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: int = 512
            Tile size to use if not defined by file.
        uid_generator: Callable[..., UID] = generate_uid
             Function that can generate unique identifiers.
        include_levels: Optional[Sequence[int]] = None
            Optional list indices (in present levels) to include, e.g. [0, 1]
            includes the two lowest levels. Negative indices can be used,
            e.g. [-1, -2] includes the two highest levels.
        include_label: bool = True
            Include label(s), default true.
        include_overwiew: bool = True
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
        encoding_quality: float = 90
            Quality to use if re-encoding. It is recommended to not use > 95 for jpeg.
            Use < 1 or > 1000 for lossless jpeg2000.
        jpeg_subsampling: str = '420'
            Subsampling option if using jpeg for re-encoding. Use '444' for
            no subsampling, '422' for 2x1 subsampling, and '420' for 2x2
            subsampling.
        offset_table: Optional[str] = 'bot'
            Offset table to use, 'bot' basic offset table, 'eot' extended
            offset table, None - no offset table.
        label: Optional[Union[PILImage, str, Path]] = None
            Optional label image to use instead of label found in file.
        preferred_source: Optional[Type[DicomizerSource]] = None
            Optional override source to use.
        **source_args
            Optional keyword args to pass to source.

        Returns
        ----------
        List[str]
            List of paths of created files.
        """
        with cls.open(
            filepath,
            metadata,
            tile_size,
            include_levels,
            include_label,
            include_overview,
            include_confidential,
            encoding_format,
            encoding_quality,
            jpeg_subsampling,
            label,
            preferred_source,
            **source_args,
        ) as wsi:
            if output_path is None:
                output_path = str(
                    Path(filepath).parents[0].joinpath(Path(filepath).stem)
                )
            try:
                os.mkdir(output_path)
            except FileExistsError:
                ValueError(f"Output path {output_path} already exists")
            created_files = wsi.save(
                output_path, uid_generator, workers, chunk_size, offset_table
            )

        return [str(filepath) for filepath in created_files]
