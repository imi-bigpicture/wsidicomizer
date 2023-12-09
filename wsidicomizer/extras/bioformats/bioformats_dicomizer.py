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

from pydicom import Dataset
from wsidicom import WsiDicom
from wsidicom.codec import Encoder, JpegSettings
from wsidicom.codec import Settings as EncodingSettings

from wsidicomizer.extras.bioformats.bioformats_source import BioformatsSource
from wsidicomizer.wsidicomizer import WsiDicomizer


class BioformatsDicomizer(WsiDicomizer):
    @classmethod
    def open(
        cls,
        filepath: Union[str, Path],
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        tile_size: int = 512,
        include_confidential: bool = True,
        encoding_settings: Optional[EncodingSettings] = None,
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
        include_confidential: bool = True
            Include confidential metadata.
        encoding: Optional[Union[EncodingSettings, Encoder]] = None,
            Encoding setting or encoder to use if re-encoding.


        Returns
        ----------
        WsiDicom
            WsiDicom object of file.
        """
        if not isinstance(filepath, Path):
            filepath = Path(filepath)

        if not BioformatsSource.is_supported(filepath):
            raise NotImplementedError(f"{filepath} is not supported")
        if encoding_settings is None:
            encoding_settings = JpegSettings()
        encoder = Encoder.create_for_settings(encoding_settings)

        dicomizer = BioformatsSource(
            filepath,
            encoder,
            tile_size,
            modules,
            include_confidential,
        )
        return cls(dicomizer)
