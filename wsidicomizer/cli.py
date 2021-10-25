import argparse
from pathlib import Path
import json
from pydicom.dataset import Dataset
from wsidicomizer.interface import WsiDicomizer
from wsidicomizer.dataset import create_default_modules


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
    args = parser.parse_args()
    if not args.dataset:
        dataset = create_default_modules()
    else:
        json_file = open(args.dataset)
        dataset = Dataset.from_json(json.load(json_file))
    if not args.levels:
        levels = None
    else:
        levels = args.levels

    WsiDicomizer.convert(
        args.input,
        args.output,
        dataset,
        tile_size=args.tile_size,
        include_levels=levels,
        include_label=not args.no_label,
        include_overview=not args.no_overview
    )
