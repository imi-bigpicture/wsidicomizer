import argparse
from pathlib import Path
import json
from pydicom.dataset import Dataset
from wsidicomizer.interface import WsiDicomizer
from wsidicomizer.dataset import create_test_base_dataset


def main():
    parser = argparse.ArgumentParser(description='Convert wsi to DICOM')

    parser.add_argument(
        '-i', '--input',
        type=Path,
        required=True,
        help='path to input wsi file'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        help='path to output folder'
    )
    parser.add_argument(
        '-t', '--tile-size',
        type=int,
        help='tile size (same for width and height)'
    )
    parser.add_argument(
        '-d', '--dataset',
        type=Path,
        help='path to json DICOM dataset'
    )
    parser.add_argument(
        '-l', '--levels',
        type=int,
        nargs='+',
        help='levels to include, if not all',
    )
    parser.add_argument(
        '--no-label',
        action="store_true",
        help='if not to include label'
    )
    parser.add_argument(
        '--nooverview',
        action="store_true",
        help='if not to include overview'
    )
    args = parser.parse_args()
    if not args.dataset:
        dataset = create_test_base_dataset()
    else:
        json_file = open(args.dataset)
        dataset = Dataset.from_json(json.load(json_file))
    if not args.levels:
        levels = None
    else:
        levels = args.levels

    WsiDicomizer.convert(
        str(args.input),
        str(args.output),
        dataset,
        tile_size=args.tile_size,
        include_levels=levels,
        include_label=not args.no_label,
        include_overview=not args.no_overview
    )
