from typing import Optional, Sequence

from pydicom import Dataset
from wsidicomizer.bioformats import BioFormatsDicomizer
from wsidicomizer.cli.wsidicomizer_cli import WsiDicomizerCli


class BioFormatsCli(WsiDicomizerCli):
    def convert(
        self,
        filepath: str,
        output_path: str,
        modules: Optional[Dataset] = None,
        tile_size: Optional[int] = 512,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        workers: Optional[int] = None,
        chunk_size: Optional[int] = None,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '420',
        offset_table: Optional[str] = 'bot'
    ):
        with BioFormatsDicomizer.open(
            filepath=filepath,
            modules=modules,
            tile_size=tile_size,
            include_levels=include_levels,
            include_label=include_label,
            include_overview=include_overview,
            encoding_format=encoding_format,
            encoding_quality=encoding_quality,
            jpeg_subsampling=jpeg_subsampling,
        ) as wsi:
            wsi.save(
                output_path=output_path,
                offset_table=offset_table,
                workers=workers,
                chunk_size=chunk_size
            )


def main():
    cli = BioFormatsCli()
    cli.cli()


if __name__ == "__main__":
    main()
