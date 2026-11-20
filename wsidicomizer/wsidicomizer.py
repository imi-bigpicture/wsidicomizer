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
import logging
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
    TranscodingMode,
    WsiDicom,
    WsiFile,
)
from wsidicom.codec import Encoder
from wsidicom.codec import Settings as EncodingSettings
from wsidicom.file import OffsetTableType
from wsidicom.metadata import CallableUidGenerator, UidGenerator, WsiMetadata
from wsidicom.paths import as_upath

from wsidicomizer.config import Settings, use_settings
from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.errors import SourceNotSupportedError
from wsidicomizer.metadata import (
    MetadataPostProcessor,
    MetadataPreProcessor,
)
from wsidicomizer.sources import (
    CziSource,
    MiraxSource,
    OpenTileSource,
    TiffSlideSource,
    VsiSource,
)

logger = logging.getLogger(__name__)


class SourceIdentifier(Enum):
    OPENTILE = "opentile"
    TIFFSLIDE = "tiffslide"
    OPENSLIDE = "openslide"
    CZI = "czi"
    MIRAX = "mirax"
    VSI = "vsi"
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
        metadata_pre_processor: MetadataPreProcessor | None = None,
        encoding: EncodingSettings | Encoder | None = None,
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None,
        uid_generator: Callable[[], UID] | UidGenerator | None = None,
        file_options: dict[str, Any] | None = None,
        *,
        settings: Settings | None = None,
        **source_args,
    ) -> "WsiDicomizer":
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
        metadata_pre_processor: MetadataPreProcessor | None = None
            Optional metadata pre processing by callback, of the metadata read
            from the file before `metadata` and `default_metadata` are merged
            into it.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use for transcoding. If None, each
            source picks a default matching its pixel format.
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None
            Optional override source to use. If None, the sources whose format
            the file is are tried in priority order, and the first that reads it
            is used.
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
        WsiDicomizer
            WsiDicomizer object of file.

        Raises
        ------
        SourceNotSupportedError
            If no source reads the file.
        """
        if uid_generator is None:
            uid_generator = CallableUidGenerator()
        elif not isinstance(uid_generator, UidGenerator):
            uid_generator = CallableUidGenerator(uid_generator)
        filepath = as_upath(filepath, file_options)
        candidates = cls._select_sources(filepath, preferred_source, file_options)
        encoder = cls._select_encoder(encoding)

        refusal: SourceNotSupportedError | None = None
        with use_settings(settings):
            for candidate in candidates:
                try:
                    source = candidate(
                        filepath,
                        encoder,
                        tile_size,
                        metadata,
                        default_metadata,
                        include_confidential,
                        metadata_post_processor,
                        uid_generator=uid_generator,
                        file_options=file_options,
                        metadata_pre_processor=metadata_pre_processor,
                        **source_args,
                    )
                except SourceNotSupportedError as error:
                    logger.info(
                        "%s does not read %s: %s", candidate.__name__, filepath, error
                    )
                    refusal = error
                    continue
                try:
                    return cls(source, True, settings=settings)
                except BaseException:
                    # The source is only owned once the WsiDicomizer exists, so a
                    # source that is refused while building it (e.g. several
                    # pyramids) must be closed here or its files stay open.
                    source.close()
                    raise
        raise SourceNotSupportedError(f"{filepath} is not supported") from refusal

    @classmethod
    def convert(
        cls,
        filepath: str | Path | UPath,
        output_path: str | Path | UPath,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        tile_size: int | None = 512,
        uid_generator: Callable[[], UID] | UidGenerator | None = None,
        add_missing_levels: bool | None = None,
        regenerate_pyramid: bool | None = None,
        include_levels: Sequence[int] | None = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_thumbnail: bool = True,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        metadata_pre_processor: MetadataPreProcessor | None = None,
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
        output_file_options: dict[str, Any] | None = None,
        *,
        settings: Settings | None = None,
        **source_args,
    ) -> dict[UPath, WsiFile]:
        """Convert data in file to DICOM files in output path. Created
        instances get UID from uid_generator. Closes when finished.

        Parameters
        ----------
        filepath: Union[str, Path],
            Path to file
        output_path: str | Path | UPath
            Folder path to save files to. Must not already exist, or be an
            empty folder.
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
        add_missing_levels: bool | None = None
            If to add missing dyadic levels up to the single tile level. If None,
            follows the source's `prefer_regenerated_pyramid` when `include_levels`
            is not given, so a source that stores only its base level (MIRAX) gets
            a pyramid built from it; with `include_levels`, no levels are added.
        regenerate_pyramid: bool | None = None
            If True, only the base level is read from the source and every
            other written level is re-derived by downsampling from the base.
            When set, the base level must be among the selected `include_levels`.
            If None, follows the source's `prefer_regenerated_pyramid` when
            `include_levels` is not given, and otherwise keeps the stored levels.
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
        metadata_pre_processor: MetadataPreProcessor | None = None
            Optional metadata pre processing by callback, of the metadata read
            from the file before `metadata` and `default_metadata` are merged
            into it.
        workers: Optional[int] = None,
            Maximum number of thread workers to use.
        chunk_size: Optional[int] = None,
            Chunk size (number of tiles) to process at a time. Actual chunk
            size also depends on minimum_chunk_size from image_data.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use for images that cannot be passed
            through, or for all images if `force_transcoding=True`. If None,
            each source picks a default matching its pixel format. With
            `JpegSettings(optimize=True)`, JPEG Baseline images that are passed
            through also get optimized Huffman tables, without changing their
            pixels. Images in other transfer syntaxes are still passed through.
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
            (`ConcatenationByFrames(n)`) or byte size (`ConcatenationByBytes(size)`,
            where `size` is an int or a suffixed string such as `"100M"` or `"2GB"`).
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None
            Optional override source to use.
        file_options: dict[str, Any] | None = None
            Options forwarded to the fsspec filesystem when reading the input
            (e.g. credentials), and to the output unless `output_file_options`
            is set. Ignored by sources that read local files.
        output_file_options: dict[str, Any] | None = None
            Options forwarded to the fsspec filesystem when writing the output.
            Set this when the output lives on a different filesystem than the
            input. Defaults to `file_options`.
        settings: Settings | None = None
            Settings to use for this conversion instead of the process-wide default.
        **source_args
            Optional keyword args to pass to source.

        Returns
        ----------
        dict[UPath, WsiFile]
            The created files, by path, in the order they were written. The
            paths are configured with `output_file_options` so that they can be
            opened as returned. Each file is described as written: a
            `WsiLevelFile` for a pyramid level, a `WsiThumbnailFile`
            for a thumbnail, and a `WsiAssociatedFile` for a label or
            overview. Iterating gives the paths.
        """
        if uid_generator is None:
            uid_generator = CallableUidGenerator()
        elif not isinstance(uid_generator, UidGenerator):
            uid_generator = CallableUidGenerator(uid_generator)
        if output_file_options is None:
            output_file_options = file_options
        with (
            use_settings(settings),
            cls.open(
                filepath,
                metadata,
                default_metadata,
                tile_size,
                include_confidential,
                metadata_post_processor,
                metadata_pre_processor,
                encoding,
                preferred_source,
                uid_generator,
                file_options,
                settings=settings,
                **source_args,
            ) as wsi,
        ):
            if regenerate_pyramid is None:
                regenerate_pyramid = include_levels is None and (
                    wsi._prefer_regenerated_pyramid
                )
            if add_missing_levels is None:
                add_missing_levels = include_levels is None and (
                    wsi._prefer_regenerated_pyramid
                )
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
                transcoding=encoding,
                transcoding_mode=(
                    TranscodingMode.ALWAYS
                    if force_transcoding
                    else TranscodingMode.WHEN_REQUIRED
                ),
                instance_split=instance_split,
                concatenation=concatenation,
                file_options=output_file_options,
            )

        return created_files

    @property
    def _prefer_regenerated_pyramid(self) -> bool:
        """Return True if the source prefers its pyramid to be re-derived from the
        base level on conversion."""
        return (
            isinstance(self._source, DicomizerSource)
            and self._source.prefer_regenerated_pyramid
        )

    @staticmethod
    def _select_sources(
        filepath: UPath,
        preferred_source: type[DicomizerSource] | SourceIdentifier | None = None,
        file_options: dict[str, Any] | None = None,
    ) -> list[type[DicomizerSource]]:
        """Return the sources whose format the file in filepath is, in priority
        order, or only the preferred source if one is given.

        Raises
        ------
        SourceNotSupportedError
            If no source is of the file's format.
        """
        # List of supported sources in prioritization order.
        loaded_sources: dict[SourceIdentifier, type[DicomizerSource]] = {
            SourceIdentifier.OPENTILE: OpenTileSource,
            # Before tiffslide, as the .vsi is a TIFF that tiffslide opens but
            # that holds only associated images, not the pyramid.
            SourceIdentifier.VSI: VsiSource,
            SourceIdentifier.TIFFSLIDE: TiffSlideSource,
            SourceIdentifier.CZI: CziSource,
            # Before openslide, so the native MIRAX reader wins.
            SourceIdentifier.MIRAX: MiraxSource,
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
            try:
                preferred_source = loaded_sources[preferred_source]
            except KeyError:
                raise ValueError(
                    f"Source {preferred_source.value} is not available. It needs the "
                    f"'{preferred_source.value}' extra to be installed."
                ) from None
        sources = (
            list(loaded_sources.values())
            if preferred_source is None
            else [preferred_source]
        )
        selected_sources = [
            source for source in sources if source.is_supported(filepath, file_options)
        ]
        if not selected_sources:
            raise SourceNotSupportedError(f"{filepath} is not supported")
        return selected_sources

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
