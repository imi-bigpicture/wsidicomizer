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

from abc import ABCMeta, abstractmethod
from copy import deepcopy
from typing import Optional, Sequence, Union

import numpy as np
from pydicom import Dataset, config
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import (JPEG2000, JPEG2000Lossless, JPEGBaseline8Bit,
                         generate_uid)
from pydicom.valuerep import DSfloat
from wsidicom import ImageData, WsiDicom, WsiInstance
from wsidicom.image_data import ImageOrigin
from wsidicom.instance import WsiDataset

from wsidicomizer.encoding import Encoder

from .dataset import get_image_type

config.enforce_valid_values = True
config.future_behavior()


class MetaImageData(ImageData, metaclass=ABCMeta):
    _default_z = None

    def __init__(
        self,
        encoder: Encoder
    ):
        """Metaclass for Dicomized image data.

        Parameters
        ----------
        encoded: Encoder
            Encoder to use.
        """
        self._encoder = encoder

    @property
    @abstractmethod
    def pyramid_index(self) -> int:
        """Should return pyramid level for image data."""
        raise NotImplementedError()

    @property
    def image_origin(self) -> ImageOrigin:
        """Return a default ImageOrigin."""
        return ImageOrigin()

    def create_instance_dataset(
        self,
        base_dataset: Dataset,
        image_flavor: str,
        instance_number: int,
        image_data: ImageData
    ) -> WsiDataset:
        """Return instance dataset for image_data based on base dataset.

        Parameters
        ----------
        base_dataset: Dataset
            Dataset common for all instances.
        image_flavor:
            Type of instance ('VOLUME', 'LABEL', 'OVERVIEW)
        instance_number: int
        image_data:
            Image data to crate dataset for.

        Returns
        ----------
        WsiDataset
            Dataset for instance.
        """
        dataset = deepcopy(base_dataset)
        dataset.ImageType = get_image_type(
            image_flavor,
            self.pyramid_index
        )
        dataset.SOPInstanceUID = generate_uid(prefix=None)
        shared_functional_group_sequence = Dataset()
        if self.pixel_spacing is None:
            if image_flavor == 'VOLUME':
                raise ValueError(
                    "Image flavor 'VOLUME' requires pixel spacing to be set"
                )
        else:

            pixel_measure_sequence = Dataset()
            pixel_measure_sequence.PixelSpacing = [
                DSfloat(self.pixel_spacing.width, True),
                DSfloat(self.pixel_spacing.height, True)
            ]
            pixel_measure_sequence.SpacingBetweenSlices = 0.0
            # DICOM 2022a part 3 IODs - C.8.12.4.1.2 Imaged Volume Width,
            # Height, Depth. Depth must not be 0. Default to 0.5 microns
            pixel_measure_sequence.SliceThickness = 0.0005
            shared_functional_group_sequence.PixelMeasuresSequence = (
                DicomSequence([pixel_measure_sequence])
            )
            dataset.SharedFunctionalGroupsSequence = DicomSequence(
                [shared_functional_group_sequence]
            )
            dataset.ImagedVolumeWidth = (
                self.image_size.width * self.pixel_spacing.width
            )
            dataset.ImagedVolumeHeight = (
                self.image_size.height * self.pixel_spacing.height
            )
            dataset.ImagedVolumeDepth = pixel_measure_sequence.SliceThickness
            # DICOM 2022a part 3 IODs - C.8.12.9 Whole Slide Microscopy Image
            # Frame Type Macro. Analogous to ImageType and shared by all
            # frames so clone
            wsi_frame_type_item = Dataset()
            wsi_frame_type_item.FrameType = dataset.ImageType
            (
                shared_functional_group_sequence.
                WholeSlideMicroscopyImageFrameTypeSequence
            ) = (
                DicomSequence([wsi_frame_type_item])
            )

        dataset.DimensionOrganizationType = 'TILED_FULL'
        dataset.TotalPixelMatrixColumns = self.image_size.width
        dataset.TotalPixelMatrixRows = self.image_size.height
        dataset.Columns = self.tile_size.width
        dataset.Rows = self.tile_size.height
        dataset.NumberOfFrames = (
            self.tiled_size.width
            * self.tiled_size.height
        )

        if image_data.transfer_syntax == JPEGBaseline8Bit:
            dataset.BitsAllocated = 8
            dataset.BitsStored = 8
            dataset.HighBit = 7
            dataset.PixelRepresentation = 0
            dataset.LossyImageCompression = '01'
            dataset.LossyImageCompressionRatio = 1
            dataset.LossyImageCompressionMethod = 'ISO_10918_1'
            dataset.LossyImageCompression = '01'
        elif image_data.transfer_syntax == JPEG2000:
            # TODO JPEG2000 can have higher bitcount
            dataset.BitsAllocated = 8
            dataset.BitsStored = 8
            dataset.HighBit = 7
            dataset.PixelRepresentation = 0
            # dataset.LossyImageCompressionRatio = 1
            dataset.LossyImageCompressionMethod = 'ISO_15444_1'
            dataset.LossyImageCompression = '01'
        elif image_data.transfer_syntax == JPEG2000Lossless:
            # TODO JPEG2000 can have higher bitcount
            dataset.BitsAllocated = 8
            dataset.BitsStored = 8
            dataset.HighBit = 7
            dataset.PixelRepresentation = 0
            dataset.LossyImageCompression = '00'
        else:
            raise ValueError("Non-supported transfer syntax.")

        dataset.PhotometricInterpretation = (
            image_data.photometric_interpretation
        )
        dataset.SamplesPerPixel = image_data.samples_per_pixel

        dataset.PlanarConfiguration = 0

        dataset.InstanceNumber = instance_number
        dataset.FocusMethod = 'AUTO'
        dataset.ExtendedDepthOfField = 'NO'
        return WsiDataset(dataset)

    def _encode(
        self,
        image_data: np.ndarray
    ) -> bytes:
        """Return image data encoded in jpeg using set quality and subsample
        options.

        Parameters
        ----------
        image_data: np.ndarray
            Image data to encode.

        Returns
        ----------
        bytes
            Jpeg bytes.
        """
        return self._encoder.encode(image_data)


class MetaDicomizer(WsiDicom, metaclass=ABCMeta):
    """Metaclass for Dicomizers. Subclasses should implement is_supported() and
    open().
    """
    @staticmethod
    @abstractmethod
    def is_supported(path: str) -> bool:
        """Return True if file in filepath is supported by Dicomizer."""
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def open(
        cls,
        filepath: str,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        tile_size: Optional[int] = 512,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '420'
    ) -> WsiDicom:
        """Open file in filepath as WsiDicom object. Note that created
        instances always has a random UID.

        Parameters
        ----------
        filepath: str
            Path to tiff file
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None
            Module datasets to use in files. If none, use default modules.
        tile_size: Optional[int] = 512
            Tile size to use if not defined by file.
        include_levels: Sequence[int] = None
            Pyramid levels to include. If None, include all levels.
            Use negative indices to specify reverse indexing from highest
            level.
        include_label: bool = True
            Inclube label.
        include_overview: bool = True
            Include overview.
        include_confidential: bool = True
            Include confidential metadata.
        encoding_format: str = 'jpeg'
            Encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'.
        encoding_quality: int = 90
            Quality to use if re-encoding. Do not use > 95 for jpeg. Use 100
            for lossless jpeg2000.
        jpeg_subsampling: str = '420'
            Subsampling option if using jpeg for re-encoding. Use '444' for
            no subsampling, '422' for 2x1 subsampling, and '420' for 2x2
            subsampling.

        Returns
        ----------
        WsiDicom
            WsiDicom object of file in filepath.
        """
        raise NotImplementedError()

    @staticmethod
    def _create_instance(
        image_data: MetaImageData,
        base_dataset: Dataset,
        image_type: str,
        instance_number: int
    ) -> WsiInstance:
        """Create WsiInstance from MetaImageData.

        Parameters
        ----------
        image_data: ImageData
            Image data and metadata.
        base_dataset: Dataset
            Base dataset to include.
        image_type: str
            Type of instance to create.
        instance_number: int
            The number of the instance (in a series).

        Returns
        ----------
        WsiInstance
            Created WsiInstance.
        """
        instance_dataset = image_data.create_instance_dataset(
            base_dataset,
            image_type,
            instance_number,
            image_data
        )

        return WsiInstance(
            instance_dataset,
            image_data
        )

    @staticmethod
    def _is_included_level(
        level: int,
        present_levels: Sequence[int],
        include_levels: Optional[Sequence[int]] = None
    ) -> bool:
        """Return true if pyramid level is in included levels."""
        if include_levels is None:
            return True

        absolute_levels = [present_levels[level] for level in include_levels]
        return level in absolute_levels
