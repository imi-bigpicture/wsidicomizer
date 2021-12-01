from abc import ABCMeta, abstractmethod
from wsidicom import WsiDicom, WsiInstance, WsiDataset
from wsidicomizer.imagedata_wrapper import ImageDataWrapper
from pydicom import Dataset
from typing import Optional, Union, Sequence


class MetaDicomizer(WsiDicom, metaclass=ABCMeta):
    @staticmethod
    @abstractmethod
    def is_supported(path: str) -> bool:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def open(
        cls,
        filepath: str,
        modules: Optional[Union[Dataset, Sequence[Dataset]]] = None,
        tile_size: Optional[int] = None,
        include_levels: Optional[Sequence[int]] = None,
        include_label: bool = True,
        include_overview: bool = True,
        include_confidential: bool = True,
        encoding_format: str = 'jpeg',
        encoding_quality: int = 90,
        jpeg_subsampling: str = '422'
    ) -> WsiDicom:
        raise NotImplementedError()

    @staticmethod
    def _create_instance(
        image_data: ImageDataWrapper,
        base_dataset: Dataset,
        image_type: str,
        instance_number: int
    ) -> WsiInstance:
        """Create WsiInstance from ImageDataWrapper.

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
            image_data.transfer_syntax,
            image_data.photometric_interpretation
        )

        return WsiInstance(
            instance_dataset,
            image_data
        )
