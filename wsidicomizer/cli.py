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
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click
from wsidicom import ConcatenationByBytes, ConcatenationByFrames, InstanceSplit
from wsidicom.codec.settings import (
    HTJpeg2000Settings,
    Jpeg2kSettings,
    JpegSettings,
    JpegXlSettings,
    Subsampling,
)
from wsidicom.file import OffsetTableType
from wsidicom.metadata.schema.json.wsi import WsiMetadataJsonSchema
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.wsidicomizer import SourceIdentifier, WsiDicomizer


class CliEncodingsOptions(Enum):
    JPEG = "jpeg"
    JPEG2000 = "jpeg2000"
    HTJPEG2000 = "htjpeg2000"
    JPEGXL = "jpegxl"


# Distribution names (not import names) of the packages wsidicomizer is tightly
# coupled to: core, source readers, and codecs. Optional ones may be absent.
_VERSION_PACKAGES = [
    "wsidicomizer",
    "wsidicom",
    "opentile",
    "pydicom",
    "tiffslide",
    "tifffile",
    "imagecodecs",
    "czifile",
    "openslide-python",
    "pyisyntax",
]


def _print_versions(ctx: click.Context, _param: click.Parameter, value: bool):
    if not value or ctx.resilient_parsing:
        return
    width = max(len(name) for name in _VERSION_PACKAGES)
    for name in _VERSION_PACKAGES:
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = "not installed"
        click.echo(f"{name.ljust(width)}  {installed}")
    ctx.exit()


@click.command()
@click.version_option(package_name="wsidicomizer")
@click.option(
    "--versions",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_versions,
    help="Show versions of wsidicomizer and its key dependencies, then exit.",
)
@click.option(
    "-i",
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to input wsi file.",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help=(
        "Path to output folder. Folder will be created and must not "
        "exist. If not specified a folder named after the input file "
        "is created in the same path."
    ),
)
@click.option(
    "-t",
    "--tile-size",
    type=int,
    default=512,
    help=(
        "Output tile size (same for width and height). Has no effect on "
        "sources that read native tiles (opentile non-NDPI, isyntax)."
    ),
)
@click.option(
    "-m",
    "--metadata",
    type=click.Path(exists=True, path_type=Path),
    help=("Path to json metadata that will override metadata from source image file."),
)
@click.option(
    "-d",
    "--default-metadata",
    type=click.Path(exists=True, path_type=Path),
    help="Path to json metadata that will be used as default values.",
)
@click.option(
    "-l",
    "--levels",
    type=int,
    multiple=True,
    help=(
        "Pyramid levels to include, if not all. E.g. 0 1 for base and "
        "first pyramid layer. Can be specified multiple times."
    ),
)
@click.option(
    "--add-missing-levels",
    is_flag=True,
    help="If to add missing dyadic levels up to the single tile level.",
)
@click.option(
    "--regenerate-pyramid",
    is_flag=True,
    help=(
        "Read only the base level from the source and re-derive every other "
        "written level by downsampling from it."
    ),
)
@click.option(
    "--split-focal-planes",
    is_flag=True,
    help="Write a separate instance per focal plane.",
)
@click.option(
    "--split-optical-paths",
    is_flag=True,
    help="Write a separate instance per optical path.",
)
@click.option(
    "--concatenate-frames",
    type=int,
    default=None,
    help="Split each level into concatenated instances of at most this many frames "
    "each. Mutually exclusive with --concatenate-bytes.",
)
@click.option(
    "--concatenate-bytes",
    type=str,
    default=None,
    help="Split each level into concatenated instances whose pixel data is at most "
    "this size each (e.g. for DICOMweb STOW size limits). A plain byte count, "
    "optionally with a binary suffix: '5000000', '500KB', '100M', '2GB'. Mutually "
    "exclusive with --concatenate-frames.",
)
@click.option(
    "--label",
    type=click.Path(exists=True, path_type=Path),
    help="Optional label image to use instead of label found in file.",
)
@click.option("--no-label", is_flag=True, help="If not to include label")
@click.option("--no-overview", is_flag=True, help="If not to include overview")
@click.option(
    "--no-confidential", is_flag=True, help="If not to include confidential metadata"
)
@click.option(
    "-w",
    "--workers",
    type=int,
    default=os.cpu_count(),
    help="Number of worker threads to use",
)
@click.option(
    "--chunk-size",
    type=int,
    default=100,
    help="Number of tiles to give each worker at a time",
)
@click.option(
    "--format",
    "encoding_format",
    type=click.Choice(CliEncodingsOptions, case_sensitive=False),
    default=CliEncodingsOptions.JPEG,
    help=(
        "Encoding format to use if lossless conversion not possible or if "
        "forcing transcoding."
    ),
)
@click.option(
    "--quality",
    type=float,
    default=None,
    help=(
        "Quality to use for encoding. It is not recommended to use > 95 for "
        "jpeg. Use < 1 or > 1000 for lossless jpeg2000."
    ),
)
@click.option(
    "--subsampling",
    type=click.Choice(Subsampling, case_sensitive=False),
    default=None,
    help=(
        "Subsampling option if using jpeg for encoding. Use '444' "
        "for no subsampling, '422' for 2x1 subsampling, and '420' for "
        "2x2 subsampling."
    ),
)
@click.option(
    "--force-transcoding",
    is_flag=True,
    help="If to force transcoding even if lossless conversion possible.",
)
@click.option(
    "--offset-table",
    type=click.Choice(
        [OffsetTableType.BASIC, OffsetTableType.EXTENDED, OffsetTableType.EMPTY],
        case_sensitive=False,
    ),
    default=OffsetTableType.BASIC,
    help=("Offset table to use."),
)
@click.option(
    "--source",
    type=click.Choice(SourceIdentifier, case_sensitive=False),
    default=None,
    help=(
        "Source library to use for reading the input file. If not specified, "
        "the library will be chosen based on file type."
    ),
)
def main(
    input_path: Path,
    output_path: Path | None,
    tile_size: int,
    metadata: Path | None,
    default_metadata: Path | None,
    levels: tuple[int, ...],
    add_missing_levels: bool,
    regenerate_pyramid: bool,
    split_focal_planes: bool,
    split_optical_paths: bool,
    concatenate_frames: int | None,
    concatenate_bytes: str | None,
    label: Path | None,
    no_label: bool,
    no_overview: bool,
    no_confidential: bool,
    workers: int,
    chunk_size: int,
    encoding_format: CliEncodingsOptions | None,
    quality: float | None,
    subsampling: str | None,
    force_transcoding: bool,
    offset_table: OffsetTableType,
    source: SourceIdentifier | None,
):
    """Convert compatible wsi file to DICOM.

    The cli only supports a subset of the functionality of the WsiDicomizer
    class. For more advanced usage, use the class directly.
    """

    # Load metadata if provided
    loaded_metadata = None
    if metadata:
        loaded_metadata = _load_metadata(metadata)

    loaded_default_metadata = None
    if default_metadata:
        loaded_default_metadata = _load_metadata(default_metadata)

    # Convert levels tuple to list or None
    include_levels = list(levels) if levels else None

    instance_split = InstanceSplit.NONE
    if split_focal_planes:
        instance_split |= InstanceSplit.FOCAL_PLANE
    if split_optical_paths:
        instance_split |= InstanceSplit.OPTICAL_PATH

    if concatenate_frames is not None and concatenate_bytes is not None:
        raise click.UsageError(
            "Use at most one of --concatenate-frames / --concatenate-bytes."
        )
    concatenation = None
    try:
        if concatenate_frames is not None:
            concatenation = ConcatenationByFrames(concatenate_frames)
        elif concatenate_bytes is not None:
            concatenation = ConcatenationByBytes(concatenate_bytes)
    except ValueError as error:
        raise click.UsageError(str(error)) from error

    # Create encoding settings
    if encoding_format is None:
        encoding_settings = None
    elif encoding_format == CliEncodingsOptions.JPEG:
        subsampling_enum = (
            Subsampling.from_string(subsampling)
            if subsampling is not None
            else Subsampling.R420
        )
        encoding_settings = JpegSettings(
            quality=int(quality) if quality else 80, subsampling=subsampling_enum
        )
    elif encoding_format == CliEncodingsOptions.JPEG2000:
        encoding_settings = Jpeg2kSettings(levels=[int(quality) if quality else 80])
    elif encoding_format == CliEncodingsOptions.HTJPEG2000:
        encoding_settings = HTJpeg2000Settings(levels=[int(quality) if quality else 80])
    elif encoding_format == CliEncodingsOptions.JPEGXL:
        encoding_settings = JpegXlSettings(level=int(quality) if quality else 90)
    else:
        raise ValueError(f"Unsupported encoding format {encoding_format}")

    WsiDicomizer.convert(
        filepath=input_path,
        output_path=output_path,
        metadata=loaded_metadata,
        default_metadata=loaded_default_metadata,
        tile_size=tile_size,
        add_missing_levels=add_missing_levels,
        regenerate_pyramid=regenerate_pyramid,
        include_levels=include_levels,
        include_label=not no_label,
        include_overview=not no_overview,
        include_confidential=not no_confidential,
        workers=workers,
        chunk_size=chunk_size,
        encoding=encoding_settings,
        force_transcoding=force_transcoding,
        offset_table=offset_table,
        instance_split=instance_split,
        concatenation=concatenation,
        label=label,
        preferred_source=source,
    )


def _load_metadata(filepath: Path) -> WsiMetadata:
    with open(filepath) as json_file:
        metadata = WsiMetadataJsonSchema().loads(json_file.read())
        assert isinstance(metadata, WsiMetadata)
        return metadata


if __name__ == "__main__":
    main()
