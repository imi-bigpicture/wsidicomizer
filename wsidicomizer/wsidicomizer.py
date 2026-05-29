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

import contextlib
import os
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path
from typing import Union

from PIL.Image import Image
from pydicom import Dataset
from pydicom.uid import UID, generate_uid
from wsidicom import WsiDicom
from wsidicom.codec import Encoder, JpegSettings
from wsidicom.codec import Settings as EncodingSettings
from wsidicom.file import OffsetTableType
from wsidicom.metadata import WsiMetadata

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.metadata import MetadataPostProcessor
from wsidicomizer.sources import CziSource, OpenTileSource, TiffSlideSource


class SourceIdentifier(Enum):
    OPENTILE = "opentile"
    TIFFSLIDE = "tiffslide"
    OPENSLIDE = "openslide"
    CZI = "czi"
    ISYNTAX = "isyntax"
    BIOFORMATS = "bioformats"


class WsiDicomizer(WsiDicom):
    """Interface for Dicomizing files."""

    @classmethod
    def open(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        filepath: str | Path,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        tile_size: int | None = 512,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        encoding: EncodingSettings | Encoder | None = None,
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None,
        **source_args,
    ) -> WsiDicom:
        """Open data in file in filepath as WsiDicom.

        Parameters
        ----------
        filepath: str
            Path to file
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        tile_size: Optional[int] = 512
            Tile size to use if not defined by file.
        include_confidential: bool = True
            Include confidential metadata.
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None
            Optional metadata post processing by update from dataset or callback.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use for transcoding.
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None
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
        selected_source = cls._select_source(filepath, preferred_source)
        encoder = cls._select_encoder(encoding)

        source = selected_source(
            filepath,
            encoder,
            tile_size,
            metadata,
            default_metadata,
            include_confidential,
            metadata_post_processor,
            **source_args,
        )
        return cls(source, True)

    @classmethod
    def convert(
        cls,
        filepath: str | Path,
        output_path: str | Path | None = None,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        tile_size: int | None = 512,
        uid_generator: Callable[..., UID] = generate_uid,
        add_missing_levels: bool = False,
        include_levels: Sequence[int] | None = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_thumbnail: bool = True,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        label: Image | str | Path | None = None,
        workers: int | None = None,
        chunk_size: int | None = None,
        encoding: Encoder | EncodingSettings | None = None,
        force_transcoding: bool = False,
        offset_table: Union["str", OffsetTableType] = OffsetTableType.BASIC,
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None,
        **source_args,
    ) -> list[str]:
        """Convert data in file to DICOM files in output path. Created
        instances get UID from uid_generator. Closes when finished.

        Parameters
        ----------
        filepath: Union[str, Path],
            Path to file
        output_path: str = None
            Folder path to save files to.
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        tile_size: Optional[int] = 512
            Tile size to use if not defined by file.
        uid_generator: Callable[..., UID] = generate_uid
             Function that can generate unique identifiers.
        add_missing_levels: bool = False
            If to add missing dyadic levels up to the single tile level.
        include_levels: Optional[Sequence[int]] = None
            Optional list indices (in present levels) to include, e.g. [0, 1]
            includes the two lowest levels. Negative indices can be used,
            e.g. [-1, -2] includes the two highest levels.
        include_label: bool = True
            Include label(s), default true.
        include_overwiew: bool = True
            Include overview(s), default true.
        include_thumbnail: bool = True
            Include thumbnail(s), default true.
        include_confidential: bool = True
            Include confidential metadata.
        label: Optional[Union[Image, str, Path]] = None,
            Optional label image to use instead of label found in file.
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None
            Optional metadata post processing by update from dataset or callback.
        workers: Optional[int] = None,
            Maximum number of thread workers to use.
        chunk_size: Optional[int] = None,
            Chunk size (number of tiles) to process at a time. Actual chunk
            size also depends on minimun_chunk_size from image_data.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use for images that cannot be passed
            through, or for all images if `force_transcoding=True`.
        force_transcoding: bool = False,
            If True, re-encode images using `encoding` even when the source
            transfer syntax is DICOM-compatible. Has no effect if `encoding` is
            None.
        offset_table: Union["str", OffsetTableType] = OffsetTableType.BASIC,
            Offset table to use, 'bot' basic offset table, 'eot' extended
            offset table, 'empty' - empty offset table.
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None
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
            default_metadata,
            tile_size,
            include_confidential,
            metadata_post_processor,
            encoding,
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
                output_path,
                uid_generator,
                workers,
                chunk_size,
                offset_table,
                include_levels=include_levels,
                include_labels=include_label,
                include_overviews=include_overview,
                include_thumbnails=include_thumbnail,
                add_missing_levels=add_missing_levels,
                label=label,
                transcoding=encoding if force_transcoding else None,
                force_transcoding=force_transcoding,
            )

        return [str(filepath) for filepath in created_files]

    @staticmethod
    def _select_source(
        filepath: Path,
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None,
    ) -> type[DicomizerSource]:
        """Return source that supports file in filepath."""
        # List of supported sources in prioritization order.
        loaded_sources: dict[SourceIdentifier, type[DicomizerSource]] = {
            SourceIdentifier.OPENTILE: OpenTileSource,
            SourceIdentifier.TIFFSLIDE: TiffSlideSource,
            SourceIdentifier.CZI: CziSource,
        }
        try:
            from wsidicomizer.extras.isyntax import ISyntaxSource

            loaded_sources[SourceIdentifier.ISYNTAX] = ISyntaxSource
        except ImportError:
            pass

        try:
            from wsidicomizer.extras.openslide import OpenSlideSource

            loaded_sources[SourceIdentifier.OPENSLIDE] = OpenSlideSource
        except ImportError:
            pass
        if isinstance(preferred_source, SourceIdentifier):
            if preferred_source == SourceIdentifier.BIOFORMATS:
                # Only load if requested as it requires java runtime.
                with contextlib.suppress(ImportError):
                    from wsidicomizer.extras.bioformats import BioformatsSource

                    loaded_sources[SourceIdentifier.BIOFORMATS] = BioformatsSource
            preferred_source = loaded_sources[preferred_source]
        selected_source = None
        if preferred_source is None:
            selected_source = next(
                (
                    source
                    for source in loaded_sources.values()
                    if source.is_supported(filepath)
                ),
                None,
            )
        elif preferred_source.is_supported(filepath):
            selected_source = preferred_source
        if selected_source is None:
            raise NotImplementedError(f"{filepath} is not supported")
        return selected_source

    @staticmethod
    def _select_encoder(
        encoding: Encoder | EncodingSettings | None = None,
    ) -> Encoder:
        """Return encoder from encoding."""
        if encoding is None:
            encoding = JpegSettings()
        if isinstance(encoding, EncodingSettings):
            encoder = Encoder.create_for_settings(encoding)
        else:
            encoder = encoding
        return encoder
