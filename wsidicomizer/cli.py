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
from pathlib import Path
from typing import Optional, Tuple

import click
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


@click.command()
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
        "Tile size (same for width and height). Required for ndpi and "
        "openslide formats."
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
    help="Encoding format to use if re-encoding.",
)
@click.option(
    "--quality",
    type=float,
    default=None,
    help=(
        "Quality to use if re-encoding. It is not recommended to use > 95 for "
        "jpeg. Use < 1 or > 1000 for lossless jpeg2000."
    ),
)
@click.option(
    "--subsampling",
    type=click.Choice(Subsampling, case_sensitive=False),
    default=None,
    help=(
        "Subsampling option if using jpeg for re-encoding. Use '444' "
        "for no subsampling, '422' for 2x1 subsampling, and '420' for "
        "2x2 subsampling."
    ),
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
    output_path: Optional[Path],
    tile_size: int,
    metadata: Optional[Path],
    default_metadata: Optional[Path],
    levels: Tuple[int, ...],
    add_missing_levels: bool,
    label: Optional[Path],
    no_label: bool,
    no_overview: bool,
    no_confidential: bool,
    workers: int,
    chunk_size: int,
    encoding_format: CliEncodingsOptions,
    quality: Optional[float],
    subsampling: Optional[str],
    offset_table: OffsetTableType,
    source: Optional[SourceIdentifier] = None,
):
    """Convert compatible wsi file to DICOM. The cli only supports a subset of the functionality
    of the WsiDicomizer class. For more advanced usage, use the class directly."""

    # Load metadata if provided
    loaded_metadata = None
    if metadata:
        loaded_metadata = _load_metadata(metadata)

    loaded_default_metadata = None
    if default_metadata:
        loaded_default_metadata = _load_metadata(default_metadata)

    # Convert levels tuple to list or None
    include_levels = list(levels) if levels else None

    # Create encoding settings
    encoding_settings = None
    if encoding_format == CliEncodingsOptions.JPEG:
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
        include_levels=include_levels,
        include_label=not no_label,
        include_overview=not no_overview,
        include_confidential=not no_confidential,
        workers=workers,
        chunk_size=chunk_size,
        encoding=encoding_settings,
        offset_table=offset_table,
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
