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

"""Cli for bioformats source."""

from typing import Optional, Sequence, Union

from wsidicom.codec import Settings
from wsidicom.file import OffsetTableType
from wsidicom.metadata.wsi import WsiMetadata

from wsidicomizer.cli import WsiDicomizerCli
from wsidicomizer.extras.bioformats.bioformats_dicomizer import BioformatsDicomizer


class BioformatsCli(WsiDicomizerCli):
    def convert(
        self,
        filepath: str,
        output_path: str,
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
        offset_table: Union["str", OffsetTableType] = OffsetTableType.BASIC,
    ):
        with BioformatsDicomizer.open(
            filepath=filepath,
            metadata=metadata,
            default_metadata=default_metadata,
            tile_size=tile_size,
            encoding_settings=encoding_settings,
        ) as wsi:
            wsi.save(
                output_path=output_path,
                offset_table=offset_table,
                workers=workers,
                chunk_size=chunk_size,
                include_levels=include_levels,
                include_labels=include_label,
                include_overviews=include_overview,
            )


def main():
    cli = BioformatsCli()
    cli.cli()


if __name__ == "__main__":
    main()
