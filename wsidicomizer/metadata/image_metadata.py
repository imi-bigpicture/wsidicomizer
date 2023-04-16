from abc import ABCMeta, abstractmethod
from typing import Dict


class ImageMetadata(metaclass=ABCMeta):
    pass

    @property
    @abstractmethod
    def properties(self) -> Dict[str, str]:
        """Should return a dict of DICOM attribute names and the corresponding name in
        the class."""
        raise NotImplementedError()
