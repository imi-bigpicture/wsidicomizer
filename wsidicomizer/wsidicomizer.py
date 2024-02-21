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

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union

from PIL.Image import Image
from pydicom.uid import UID, generate_uid
from upath import UPath
from wsidicom import WsiDicom
from wsidicom.codec import Encoder, JpegSettings
from wsidicom.codec import Settings as EncodingSettings
from wsidicom.file import OffsetTableType
from wsidicom.metadata import WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.sources import CziSource, OpenTileSource, TiffSlideSource

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
        filepath: Union[str, Path, UPath],
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        tile_size: int = 512,
        include_confidential: bool = True,
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
        preferred_source: Optional[Type[DicomizerSource]] = None,
        file_options: Optional[Dict[str, Any]] = None,
        **source_args,
    ) -> WsiDicom:
        """Open data in file in filepath as WsiDicom.

        Parameters
        ----------
        filepath: Union[str, Path, UPath]
            Path to file
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        tile_size: int = 512
            Tile size to use if not defined by file.
        include_confidential: bool = True
            Include confidential metadata.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use if re-encoding.
        preferred_source: Optional[Type[DicomizerSource]] = None
            Optional override source to use.
        **source_args
            Optional keyword args to pass to source.

        Returns
        ----------
        WsiDicom
            WsiDicom object of file.
        """
        if not isinstance(filepath, UPath):
            filepath = UPath(filepath)

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
        if encoding is None:
            encoding = JpegSettings()
        if isinstance(encoding, EncodingSettings):
            encoder = Encoder.create_for_settings(encoding)
        else:
            encoder = encoding

        source = selected_source(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            file_options=file_options,
            **source_args,
        )
        return cls(source)

    @classmethod
    def convert(
        cls,
        filepath: Union[str, Path, UPath],
        output_path: Optional[Union[str, Path, UPath]] = None,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        tile_size: int = 512,
        uid_generator: Callable[..., UID] = generate_uid,
        add_missing_levels: bool = False,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        label: Optional[Union[Image, str, Path]] = None,
        workers: Optional[int] = None,
        chunk_size: Optional[int] = None,
        encoding: Optional[Union[Encoder, EncodingSettings]] = None,
        offset_table: Union["str", OffsetTableType] = OffsetTableType.BASIC,
        preferred_source: Optional[Type[DicomizerSource]] = None,
        file_options: Optional[Dict[str, Any]] = None,
        output_file_options: Optional[Dict[str, Any]] = None,
        **source_args,
    ) -> List[UPath]:
        """Convert data in file to DICOM files in output path. Created
        instances get UID from uid_generator. Closes when finished.

        Parameters
        ----------
        filepath: Union[str, Path, UPath],
            Path to file
        output_path: Optional[Union[str, Path, UPath]] = None,
            Folder path to save files to.
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
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
        label: Optional[Union[Image, str, Path]] = None,
            Optional label image to use instead of label found in file.
        workers: Optional[int] = None,
            Maximum number of thread workers to use.
        chunk_size: Optional[int] = None,
            Chunk size (number of tiles) to process at a time. Actual chunk
            size also depends on minimun_chunk_size from image_data.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use if re-encoding.
        offset_table: Union["str", OffsetTableType] = OffsetTableType.BASIC,
            Offset table to use, 'bot' basic offset table, 'eot' extended
            offset table, 'empty' - empty offset table.
        preferred_source: Optional[Type[DicomizerSource]] = None
            Optional override source to use.
        file_options: Optional[Dict[str, Any]] = None,
            Options to pass to filesystem when opening file.
        output_file_options: Optional[Dict[str, Any]] = None,
            Options to pass to filesystem when saving file.
        **source_args
            Optional keyword args to pass to source.

        Returns
        ----------
        List[UPath]
            List of paths of created files.
        """
        with cls.open(
            filepath,
            metadata,
            default_metadata,
            tile_size,
            include_confidential,
            encoding,
            preferred_source,
            file_options=file_options,
            **source_args,
        ) as wsi:
            if output_path is None:
                output_path = UPath(filepath).parent.joinpath(UPath(filepath).stem)
            else:
                output_path = UPath(output_path)
            try:
                output_path.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                ValueError(f"Output path {output_path} already exists.")
            return wsi.save(
                output_path,
                uid_generator,
                workers,
                chunk_size,
                offset_table,
                include_levels=include_levels,
                include_labels=include_label,
                include_overviews=include_overview,
                add_missing_levels=add_missing_levels,
                label=label,
                file_options=output_file_options,
            )
