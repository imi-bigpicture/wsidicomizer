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

"""Dicomizer for bioformats source."""

from pathlib import Path
from typing import Optional, Sequence, Union

from PIL.Image import Image as PILImage
from wsidicom import WsiDicom

from wsidicomizer.encoding import Encoder
from wsidicomizer.extras.bioformats.bioformats_source import BioformatsSource
from wsidicomizer.wsidicomizer import WsiDicomizer
from wsidicomizer.metadata.wsi import WsiMetadata


class BioformatsDicomizer(WsiDicomizer):
    @classmethod
    def open(
        cls,
        filepath: Union[str, Path],
        metadata: Optional[WsiMetadata] = None,
        tile_size: int = 512,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        encoding_format: str = "jpeg",
        encoding_quality: float = 90,
        jpeg_subsampling: str = "420",
        label: Optional[Union[PILImage, str, Path]] = None,
    ) -> WsiDicom:
        """Open data in file in filepath as WsiDicom.

        Parameters
        ----------
        filepath: str
            Path to file
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: int = 512
            Tile size to use if not defined by file.
        include_levels: Optional[Sequence[int]] = None
            Optional list indices (in present levels) to include, e.g. [0, 1]
            includes the two lowest levels. Negative indicies can be used,
            e.g. [-1, -2] includes the two highest levels.
        include_label: bool = True
            Include label(s), default true.
        include_overwiew: bool = True
            Include overview(s), default true.
        include_confidential: bool = True
            Include confidential metadata.
        encoding_format: str = 'jpeg'
            Encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'.
        encoding_quality: float = 90
            Quality to use if re-encoding. It is recommended to not use > 95 for jpeg.
            Use < 1 or > 1000 for lossless jpeg2000.
        jpeg_subsampling: str = '420'
            Subsampling option if using jpeg for re-encoding. Use '444' for
            no subsampling, '422' for 2x1 subsampling, and '420' for 2x2
            subsampling.
        label: Optional[Union[PILImage, str, Path]] = None
            Optional label image to use instead of label found in file.


        Returns
        ----------
        WsiDicom
            WsiDicom object of file.
        """
        if not isinstance(filepath, Path):
            filepath = Path(filepath)

        if not BioformatsSource.is_supported(filepath):
            raise NotImplementedError(f"{filepath} is not supported")
        encoder = Encoder.create_encoder(
            encoding_format, encoding_quality, subsampling=jpeg_subsampling
        )

        dicomizer = BioformatsSource(
            filepath,
            encoder,
            tile_size,
            metadata,
            include_levels,
            include_label,
            include_overview,
            include_confidential,
        )
        return cls(dicomizer, label)
