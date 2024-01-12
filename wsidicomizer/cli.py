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

import argparse
import os
from pathlib import Path
from typing import Optional, Sequence

from wsidicom.codec import Jpeg2kSettings, JpegSettings, Settings, Subsampling
from wsidicom.metadata.schema.json.wsi import WsiMetadataJsonSchema
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.wsidicomizer import WsiDicomizer


class WsiDicomizerCli:
    def __init__(self):
        self._parser = argparse.ArgumentParser(
            description=("Convert compatible wsi file to DICOM")
        )

        self._parser.add_argument(
            "-i", "--input", type=Path, required=True, help="Path to input wsi file."
        )
        self._parser.add_argument(
            "-o",
            "--output",
            type=Path,
            help=(
                "Path to output folder. Folder will be created and must not "
                "exist. If not specified a folder named after the input file "
                "is created in the same path."
            ),
        )
        self._parser.add_argument(
            "-t",
            "--tile-size",
            type=int,
            default=512,
            help=(
                "Tile size (same for width and height). Required for ndpi and "
                "openslide formats E.g. 512"
            ),
        )
        self._parser.add_argument(
            "-m",
            "--metadata",
            type=Path,
            help=(
                "Path to json metadata that will override metadata from source image file."
            ),
        )
        self._parser.add_argument(
            "-d",
            "--default-metadata",
            type=Path,
            help=("Path to json metadata that will be used as default values."),
        )
        self._parser.add_argument(
            "-l",
            "--levels",
            type=int,
            nargs="+",
            help=(
                "Pyramid levels to include, if not all. E.g. 0 1 for base and "
                "first pyramid layer. "
            ),
        )
        self._parser.add_argument(
            "--label",
            type=Path,
            help="Optional label image to use instead of label found in file.",
        )
        self._parser.add_argument(
            "--no-label", action="store_true", help="If not to include label"
        )
        self._parser.add_argument(
            "--no-overview", action="store_true", help="If not to include overview"
        )
        self._parser.add_argument(
            "--no-confidential",
            action="store_true",
            help="If not to include confidential metadata",
        )
        self._parser.add_argument(
            "-w",
            "--workers",
            type=int,
            default=os.cpu_count(),
            help="Number of worker threads to use",
        )
        self._parser.add_argument(
            "--chunk-size",
            type=int,
            default=100,
            help="Number of tiles to give each worker at a time",
        )
        self._parser.add_argument(
            "--format",
            type=str,
            default="jpeg",
            help="Encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'.",
        )
        self._parser.add_argument(
            "--quality",
            type=float,
            default=90,
            help=(
                "Quality to use if re-encoding. It is recommended to not use > 95 for "
                "jpeg. Use < 1 or > 1000 for lossless jpeg2000."
            ),
        )
        self._parser.add_argument(
            "--subsampling",
            type=str,
            default="420",
            help=(
                "Subsampling option if using jpeg for re-encoding. Use '444' "
                "for no subsampling, '422' for 2x1 subsampling, and '420' for "
                "2x2 subsampling."
            ),
        )
        self._parser.add_argument(
            "--offset-table",
            type=str,
            default="bot",
            help=(
                "Offset table to use, 'bot' basic offset table, 'eot' "
                "extended offset table, 'None' - no offset table."
            ),
        )

    def cli(self):
        args = self._parser.parse_args()
        if not args.metadata:
            metadata = None
        else:
            metadata = self._load_metadata(args.metadata)
        if not args.default_metadata:
            default_metadata = None
        else:
            default_metadata = self._load_metadata(args.default_metadata)
        if not args.levels:
            levels = None
        else:
            levels = args.levels
        encoding_format = args.format
        if encoding_format == "jpeg":
            subsampling = Subsampling.from_string(args.subsampling)
            encoding_settings = JpegSettings(
                quality=args.quality, subsampling=subsampling
            )
        elif encoding_format == "jpeg2000":
            encoding_settings = Jpeg2kSettings(level=args.quality)
        else:
            encoding_settings = None
        self.convert(
            filepath=args.input,
            output_path=args.output,
            metadata=metadata,
            default_metadata=default_metadata,
            tile_size=args.tile_size,
            include_levels=levels,
            include_label=not args.no_label,
            include_overview=not args.no_overview,
            include_confidential=not args.no_confidential,
            workers=args.workers,
            chunk_size=args.chunk_size,
            encoding_settings=encoding_settings,
            offset_table=args.offset_table,
            label=args.label,
        )

    def convert(
        self,
        filepath: Path,
        output_path: Path,
        metadata: Optional[WsiMetadata] = None,
        default_metadata: Optional[WsiMetadata] = None,
        tile_size: int = 512,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        workers: Optional[int] = None,
        chunk_size: Optional[int] = None,
        encoding_settings: Optional[Settings] = None,
        offset_table: str = "bot",
        label: Optional[Path] = None,
    ):
        WsiDicomizer.convert(
            filepath=filepath,
            output_path=output_path,
            metadata=metadata,
            default_metadata=default_metadata,
            tile_size=tile_size,
            include_levels=include_levels,
            include_label=include_label,
            include_overview=include_overview,
            include_confidential=include_confidential,
            workers=workers,
            chunk_size=chunk_size,
            encoding=encoding_settings,
            offset_table=offset_table,
            label=label,
        )

    @staticmethod
    def _load_metadata(filepath: Path) -> WsiMetadata:
        with open(filepath) as json_file:
            metadata = WsiMetadataJsonSchema().loads(json_file.read())
            assert isinstance(metadata, WsiMetadata)
            return metadata


def main():
    cli = WsiDicomizerCli()
    cli.cli()


if __name__ == "__main__":
    main()
