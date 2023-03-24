#    Copyright 2023 SECTRA AB
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


from typing import Optional, Sequence

from pydicom import Dataset
from wsidicomizer.bioformats.bioformats_dicomizer import BioformatsDicomizer
from wsidicomizer.cli import WsiDicomizerCli


class BioformatsCli(WsiDicomizerCli):
    def convert(
        self,
        filepath: str,
        output_path: str,
        modules: Optional[Dataset] = None,
        tile_size: int = 512,
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
        with BioformatsDicomizer.open(
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
    cli = BioformatsCli()
    cli.cli()


if __name__ == "__main__":
    main()
