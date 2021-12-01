from abc import ABCMeta, abstractmethod
from copy import deepcopy

import numpy as np
from pydicom import config
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import UID, generate_uid, JPEGBaseline8Bit
from pydicom.valuerep import DSfloat
from wsidicom import ImageData
from wsidicom.instance import WsiDataset
from wsidicomizer.encoding import Encoder

from .dataset import get_image_type

config.enforce_valid_values = True
config.future_behavior()


class ImageDataWrapper(ImageData, metaclass=ABCMeta):
    _default_z = 0

    def __init__(
        self,
        encoder: Encoder
    ):
        """Wraps a OpenTilePage to ImageData.

        Parameters
        ----------
        tiled_page: OpenTilePage
            OpenTilePage to wrap.
        encoded: Encoder
            Encoder to use.
        """
        self._encoder = encoder

    @property
    @abstractmethod
    def pyramid_index(self) -> int:
        """Should return pyramid level for image data."""
        raise NotImplementedError

    @property
    def samples_per_pixel(self) -> int:
        return 3

    @property
    def photometric_interpretation(self) -> str:
        # Should be derived from the used subsample format
        return 'YBR_FULL'

    def create_instance_dataset(
        self,
        base_dataset: Dataset,
        image_flavor: str,
        instance_number: int,
        transfer_syntax: UID,
        photometric_interpretation: str
    ) -> WsiDataset:
        """Return instance dataset for image_data based on base dataset.

        Parameters
        ----------
        base_dataset: Dataset
            Dataset common for all instances.
        image_flavor:
            Type of instance ('VOLUME', 'LABEL', 'OVERVIEW)
        instance_number: int
        transfer_syntax: UID
        photometric_interpretation: str

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
        pixel_measure_sequence = Dataset()
        pixel_measure_sequence.PixelSpacing = [
            DSfloat(self.pixel_spacing.width, True),
            DSfloat(self.pixel_spacing.height, True)
        ]
        pixel_measure_sequence.SpacingBetweenSlices = 0.0
        pixel_measure_sequence.SliceThickness = 0.0
        shared_functional_group_sequence.PixelMeasuresSequence = (
            DicomSequence([pixel_measure_sequence])
        )
        dataset.SharedFunctionalGroupsSequence = DicomSequence(
            [shared_functional_group_sequence]
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
        dataset.ImagedVolumeWidth = (
            self.image_size.width * self.pixel_spacing.width
        )
        dataset.ImagedVolumeHeight = (
            self.image_size.height * self.pixel_spacing.height
        )
        dataset.ImagedVolumeDepth = 0.0

        if transfer_syntax == JPEGBaseline8Bit:
            dataset.BitsAllocated = 8
            dataset.BitsStored = 8
            dataset.HighBit = 7
            dataset.PixelRepresentation = 0
            # dataset.LossyImageCompressionRatio = 1
            dataset.LossyImageCompressionMethod = 'ISO_10918_1'
        if photometric_interpretation == 'YBR_FULL':
            dataset.PhotometricInterpretation = photometric_interpretation
            dataset.SamplesPerPixel = 3

        dataset.PlanarConfiguration = 0

        dataset.InstanceNumber = instance_number
        dataset.FocusMethod = 'AUTO'
        dataset.ExtendedDepthOfField = 'NO'
        return WsiDataset(dataset)

    def _encode(self, image_data: np.ndarray) -> bytes:
        """Return image data encoded in jpeg using set quality and subsample
        options.

        Parameters
        ----------
        image_data: np.ndarray
            Image data to encode, in BGRA-pixel format.

        Returns
        ----------
        bytes
            Jpeg bytes.
        """
        return self._encoder.encode(image_data)
