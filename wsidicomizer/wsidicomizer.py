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
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, Union

from PIL.Image import Image
from pydicom import Dataset
from pydicom.uid import UID
from upath import UPath
from wsidicom import (
    ConcatenationByBytes,
    ConcatenationByFrames,
    InstanceSplit,
    WsiDicom,
)
from wsidicom.codec import Encoder
from wsidicom.codec import Settings as EncodingSettings
from wsidicom.file import OffsetTableType
from wsidicom.metadata import CallableUidGenerator, UidGenerator, WsiMetadata

from wsidicomizer.config import Settings, use_settings
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
        filepath: str | Path | UPath,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        tile_size: int | None = 512,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        encoding: EncodingSettings | Encoder | None = None,
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None,
        uid_generator: Callable[[], UID] | UidGenerator | None = None,
        file_options: dict[str, Any] | None = None,
        *,
        settings: Settings | None = None,
        **source_args,
    ) -> WsiDicom:
        """Open data in file in filepath as WsiDicom.

        Parameters
        ----------
        filepath: str | Path | UPath
            Path to file. May be a fsspec path (e.g. ``s3://``) for sources that
            can read through fsspec (opentile, tiffslide); sources that only read
            local files (openslide, czifile, isyntax) decline such paths.
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        tile_size: Optional[int] = 512
            Output tile size. Falls back to `get_settings().default_tile_size` if
            `None`. Has no effect on sources that read native tiles
            (`OpenTile` non-NDPI, `ISyntax`).
        include_confidential: bool = True
            Include confidential metadata.
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None
            Optional metadata post processing by update from dataset or callback.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use for transcoding. If None, each
            source picks a default matching its pixel format.
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None
            Optional override source to use.
        uid_generator: Callable[[], UID] | UidGenerator | None = None
            Generator used to populate UIDs on the metadata if not already set.
        file_options: dict[str, Any] | None = None
            Options forwarded to the fsspec filesystem when opening a fsspec
            path (e.g. credentials). Ignored by sources that read local files.
        settings: Settings | None = None
            Settings to use for this object instead of the process-wide default.
        **source_args
            Optional keyword args to pass to source.

        Returns
        ----------
        WsiDicom
            WsiDicom object of file.
        """
        if uid_generator is None:
            uid_generator = CallableUidGenerator()
        elif not isinstance(uid_generator, UidGenerator):
            uid_generator = CallableUidGenerator(uid_generator)
        filepath = cls._normalize_path(filepath)
        selected_source = cls._select_source(filepath, preferred_source, file_options)
        encoder = cls._select_encoder(encoding)

        with use_settings(settings):
            source = selected_source(
                filepath,
                encoder,
                tile_size,
                metadata,
                default_metadata,
                include_confidential,
                metadata_post_processor,
                uid_generator=uid_generator,
                file_options=file_options,
                **source_args,
            )
            return cls(source, True, settings=settings)

    @classmethod
    def convert(
        cls,
        filepath: str | Path | UPath,
        output_path: str | Path | UPath | None = None,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        tile_size: int | None = 512,
        uid_generator: Callable[[], UID] | UidGenerator | None = None,
        add_missing_levels: bool = False,
        regenerate_pyramid: bool = False,
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
        instance_split: InstanceSplit = InstanceSplit.NONE,
        concatenation: ConcatenationByFrames | ConcatenationByBytes | None = None,
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None,
        file_options: dict[str, Any] | None = None,
        *,
        settings: Settings | None = None,
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
            Output tile size. Falls back to `get_settings().default_tile_size` if
            `None`. Has no effect on sources that read native tiles
            (`OpenTile` non-NDPI, `ISyntax`).
        uid_generator: Callable[[], UID] | UidGenerator | None = None
            Generator used to populate UIDs on the metadata if not already set and to
            generate UIDs for created instances.
        add_missing_levels: bool = False
            If to add missing dyadic levels up to the single tile level.
        regenerate_pyramid: bool = False
            If True, only the base level is read from the source and every
            other written level is re-derived by downsampling from the base.
            When set, the base level must be among the selected `include_levels`.
        include_levels: Optional[Sequence[int]] = None
            Optional list indices (in present levels) to include, e.g. [0, 1]
            includes the two lowest levels. Negative indices can be used,
            e.g. [-1, -2] includes the two highest levels.
        include_label: bool = True
            Include label(s), default true.
        include_overview: bool = True
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
            size also depends on minimum_chunk_size from image_data.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use for images that cannot be passed
            through, or for all images if `force_transcoding=True`. If None,
            each source picks a default matching its pixel format.
        force_transcoding: bool = False,
            If True, re-encode images using `encoding` even when the source
            transfer syntax is DICOM-compatible. Has no effect if `encoding` is
            None.
        offset_table: Union["str", OffsetTableType] = OffsetTableType.BASIC,
            Offset table to use, 'bot' basic offset table, 'eot' extended
            offset table, 'empty' - empty offset table.
        instance_split: InstanceSplit = InstanceSplit.NONE
            Controls how optical paths and focal planes are split across output
            instances. Default combines all into one instance per level.
            `InstanceSplit.FOCAL_PLANE` and/or `InstanceSplit.OPTICAL_PATH`
            write a separate instance per focal plane and/or optical path.
        concatenation: ConcatenationByFrames | ConcatenationByBytes | None = None
            If set, split each pyramid level into concatenated instances (SOP
            Instances sharing a Concatenation UID) by frame count
            (`ConcatenationByFrames`) or byte size (`ConcatenationByBytes`).
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None
            Optional override source to use.
        file_options: dict[str, Any] | None = None
            Options forwarded to the fsspec filesystem for both the input
            (e.g. credentials) and the output. Ignored by sources that read
            local files. When `output_path` is omitted it defaults to a folder
            next to the source on the same filesystem.
        settings: Settings | None = None
            Settings to use for this conversion instead of the process-wide default.
        **source_args
            Optional keyword args to pass to source.

        Returns
        ----------
        List[str]
            List of paths of created files.
        """
        if uid_generator is None:
            uid_generator = CallableUidGenerator()
        elif not isinstance(uid_generator, UidGenerator):
            uid_generator = CallableUidGenerator(uid_generator)
        with (
            use_settings(settings),
            cls.open(
                filepath,
                metadata,
                default_metadata,
                tile_size,
                include_confidential,
                metadata_post_processor,
                encoding,
                preferred_source,
                uid_generator,
                file_options,
                settings=settings,
                **source_args,
            ) as wsi,
        ):
            if output_path is None:
                # Default to a folder next to the source, named after it. UPath
                # keeps this working for fsspec sources, where the output can
                # live on the same (possibly remote) filesystem as the input.
                source_path = UPath(filepath)
                output_path = source_path.parent / source_path.stem
            output_path = UPath(output_path)
            try:
                output_path.mkdir()
            except FileExistsError:
                raise ValueError(f"Output path {output_path} already exists") from None
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
                regenerate_pyramid=regenerate_pyramid,
                label=label,
                transcoding=encoding if force_transcoding else None,
                force_transcoding=force_transcoding,
                instance_split=instance_split,
                concatenation=concatenation,
                file_options=file_options,
            )

        return [str(filepath) for filepath in created_files]

    @staticmethod
    def _normalize_path(path: str | Path | UPath) -> Path | UPath:
        """Return `path` typed by its nature: a plain `Path` for a plain local
        path, or a `UPath` for any fsspec location (remote, `file://`, or a
        chained url such as `simplecache::s3://...`).

        This lets the type carry the meaning downstream, so a source that reads
        only local files can decline simply by rejecting `UPath`. A chained url
        is checked via its string form because `UPath` reports it with an empty
        protocol, so the protocol alone would misjudge it as local.
        """
        path = UPath(path) if isinstance(path, (str, Path)) else path
        is_plain_local_path = path.protocol == "" and "::" not in str(path)
        if is_plain_local_path:
            return Path(path)
        return path

    @staticmethod
    def _select_source(
        filepath: Path | UPath,
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None,
        file_options: dict[str, Any] | None = None,
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
                    if source.is_supported(filepath, file_options)
                ),
                None,
            )
        elif preferred_source.is_supported(filepath, file_options):
            selected_source = preferred_source
        if selected_source is None:
            raise NotImplementedError(f"{filepath} is not supported")
        return selected_source

    @staticmethod
    def _select_encoder(
        encoding: Encoder | EncodingSettings | None = None,
    ) -> Encoder | None:
        """Return encoder from encoding, or None to let the source pick a default.

        Returning None defers the choice to the source, which knows its own
        pixel format and selects a matching default (e.g. greyscale vs RGB) via
        ``DicomizerSource._default_encoder``.
        """
        if encoding is None:
            return None
        if isinstance(encoding, EncodingSettings):
            return Encoder.create_for_settings(encoding)
        return encoding
