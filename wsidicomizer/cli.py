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
import json
import os
from pathlib import Path

from pydicom.dataset import Dataset

from wsidicomizer.dataset import create_default_modules
from wsidicomizer.interface import WsiDicomizer


def main():
    parser = argparse.ArgumentParser(
        description=('Convert combatible wsi file to DICOM')
    )

    parser.add_argument(
        '-i', '--input',
        type=Path,
        required=True,
        help='Path to input wsi file.'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help=(
            'Path to output folder. Folder will be created and must not '
            'excist. If not specified a folder named after the input file is '
            'created in the same path.'
        )
    )
    parser.add_argument(
        '-t', '--tile-size',
        type=int,
        default=512,
        help=(
            'Tile size (same for width and height). Required for ndpi and '
            'openslide formats E.g. 512'
        )
    )
    parser.add_argument(
        '-d', '--dataset',
        type=Path,
        help=(
            'Path to json DICOM dataset. Can be used to define additional '
            'DICOM modules to include in the files'
        )
    )
    parser.add_argument(
        '-l', '--levels',
        type=int,
        nargs='+',
        help=(
            'Pyramid levels to include, if not all. E.g. 0 1 for base and '
            'first pyramid layer. '
        ),
    )
    parser.add_argument(
        '--no-label',
        action="store_true",
        help='If not to include label'
    )
    parser.add_argument(
        '--no-overview',
        action="store_true",
        help='If not to include overview'
    )
    parser.add_argument(
        '--no-confidential',
        action="store_true",
        help='If not to include confidential metadata'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=os.cpu_count(),
        help='Number of worker threads to use'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=100,
        help='Number of tiles to give each worker at a time'
    )
    parser.add_argument(
        '--format',
        type=str,
        default='jpeg',
        help="Encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'."
    )
    parser.add_argument(
        '--quality',
        type=int,
        default=90,
        help=(
            "Quality to use if re-encoding. Do not use > 95 for jpeg. "
            "Use 100 for lossless jpeg2000."
        )
    )
    parser.add_argument(
        '--subsampling',
        type=str,
        default='422',
        help=(
            "Subsampling option if using jpeg for re-encoding. Use '444' for "
            "no subsampling, '422' for 2x2 subsampling."
        )
    )

    args = parser.parse_args()
    if not args.dataset:
        dataset = None
    else:
        json_file = open(args.dataset)
        dataset = Dataset.from_json(json.load(json_file))
    if not args.levels:
        levels = None
    else:
        levels = args.levels

    WsiDicomizer.convert(
        filepath=args.input,
        output_path=args.output,
        modules=dataset,
        tile_size=args.tile_size,
        include_levels=levels,
        include_label=not args.no_label,
        include_overview=not args.no_overview,
        include_confidential=not args.no_confidential,
        workers=args.workers,
        chunk_size=args.chunk_size,
        encoding_format=args.format,
        encoding_quality=args.quality,
        jpeg_subsampling=args.subsampling
    )


if __name__ == "__main__":
    main()
