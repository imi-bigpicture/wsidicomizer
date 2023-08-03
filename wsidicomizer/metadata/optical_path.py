"""Optical path model."""
import struct
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Generic, Iterable, List, Optional, Type, TypeVar, Union

import numpy as np
from pydicom import Dataset
from pydicom import Sequence as DicomSequence
from wsidicom.conceptcode import (
    IlluminationCode,
    IlluminationColorCode,
    ImagePathFilterCode,
    LenseCode,
    LightPathFilterCode,
)
from wsidicom.instance import ImageType

from wsidicomizer.metadata.dicom_attribute import (
    DicomAttribute,
    DicomByteAttribute,
    DicomCodeAttribute,
    DicomNumberAttribute,
    DicomStringAttribute,
)
from wsidicomizer.metadata.model_base import ModelBase


class Lut:
    """Represents a LUT."""

    # TODO the init should take a tuple of lists that defines the LUT
    def __init__(self, lut_sequence: DicomSequence):
        """Read LUT from a DICOM LUT sequence.

        Parameters
        ----------
        size: int
            the number of entries in the table
        bits: int
            the bits for each entry (currently forced to 16)
        """
        self._lut_item = lut_sequence[0]
        length, first, bits = self._lut_item.RedPaletteColorLookupTableDescriptor
        self._length = length
        self._bits = bits
        if bits == 8:
            self._type = np.dtype(np.uint8)
        else:
            self._type = np.dtype(np.uint16)
        self._byte_format = "<HHH"  # Do we need to set endianess?
        self.table = self._parse_lut(self._lut_item)

    def array(self, mode: str) -> np.ndarray:
        """Return flattened representation of the lookup table with order
        suitable for use with Pillows point(). The lookup table is scaled to
        either 8 or 16 bit depending on mode.

        Parameters
        ----------
        mode: str
            Image mode to produce lookup table for.

        Returns
        ----------
        np.ndarray
            Lookup table ordered by rgb, rgb ...
        """
        if mode == "L" or mode == "I":
            bits = 16
        else:
            bits = 8
        return self.table.flatten() / (2**self._bits / 2**bits)

    def insert_into_ds(self, ds: Dataset) -> Dataset:
        """Codes and insert object into sequence in dataset.

        Parameters
        ----------
        ds: Dataset
           Dataset to insert into.

        Returns
        ----------
        Dataset
            Dataset with object inserted.

        """
        ds.PaletteColorLookupTableSequence = DicomSequence([self._lut_item])
        return ds

    @classmethod
    def from_ds(cls, ds: Dataset) -> Optional["Lut"]:
        if "PaletteColorLookupTableSequence" in ds:
            return cls(ds.PaletteColorLookupTableSequence)
        return None

    def get(self) -> np.ndarray:
        """Return 2D representation of the lookup table.

        Returns
        ----------
        np.ndarray
            Lookup table ordered by color x entry
        """
        return self.table

    def _parse_color(self, segmented_lut_data: bytes):
        LENGTH = 6
        parsed_table = np.ndarray((0,), dtype=self._type)
        for segment in range(int(len(segmented_lut_data) / LENGTH)):
            segment_bytes = segmented_lut_data[
                segment * LENGTH : segment * LENGTH + LENGTH
            ]
            lut_type, lut_length, lut_value = struct.unpack(
                self._byte_format, segment_bytes
            )
            if lut_type == 0:
                parsed_table = self._add_discret(parsed_table, lut_length, lut_value)
            elif lut_type == 1:
                parsed_table = self._add_linear(parsed_table, lut_length, lut_value)
            else:
                raise NotImplementedError("Unkown lut segment type")
        return parsed_table

    def _parse_lut(self, lut: Dataset) -> np.ndarray:
        """Parse a dicom Palette Color Lookup Table Sequence item.

        Parameters
        ----------
        lut: Dataset
            A Palette Color Lookup Table Sequence item
        """
        tables = [
            lut.SegmentedRedPaletteColorLookupTableData,
            lut.SegmentedGreenPaletteColorLookupTableData,
            lut.SegmentedBluePaletteColorLookupTableData,
        ]
        parsed_tables = np.zeros((len(tables), self._length), dtype=self._type)

        for color, table in enumerate(tables):
            parsed_tables[color] = self._parse_color(table)
        return parsed_tables

    @classmethod
    def _insert(cls, table: np.ndarray, segment: np.ndarray):
        """Insert a segement into the lookup table of channel.

        Parameters
        ----------
        channel: int
            The channel (r=0, g=1, b=2) to operate on
        segment: np.ndarray
            The segment to insert
        """
        table = np.append(table, segment)
        return table

    @classmethod
    def _add_discret(cls, table: np.ndarray, length: int, value: int):
        """Add a discret segement into the lookup table of channel.

        Parameters
        ----------
        channel: int
            The channel (r=0, g=1, b=2) to operate on
        length: int
            The length of the discret segment
        value: int
            The value of the deiscret segment
        """
        segment = np.full(length, value, dtype=table.dtype)
        table = cls._insert(table, segment)
        return table

    @classmethod
    def _add_linear(cls, table: np.ndarray, length: int, value: int):
        """Add a linear segement into the lookup table of channel.

        Parameters
        ----------
        channel: int
            The channel (r=0, g=1, b=2) to operate on
        length: int
            The length of the discret segment
        value: int
            The value of the deiscret segment
        """
        # Default shift segment by one to not include first value
        # (same as last value)
        start_position = 1
        # If no last value, set it to 0 and include
        # first value in segment
        try:
            last_value = table[-1]
        except IndexError:
            last_value = 0
            start_position = 0
        segment = np.linspace(
            start=last_value, stop=value, num=start_position + length, dtype=table.dtype
        )
        table = cls._insert(table, segment[start_position:])
        return table


OpticalFilterCodeType = TypeVar(
    "OpticalFilterCodeType",
    LightPathFilterCode,
    ImagePathFilterCode,
)
OpticalFilterType = TypeVar("OpticalFilterType", bound="OpticalFilter")


@dataclass
class OpticalFilter(Generic[OpticalFilterCodeType], metaclass=ABCMeta):
    """Metaclass for filter conditions for optical path"""

    filters: Iterable[OpticalFilterCodeType]
    nominal: Optional[float]
    low_pass: Optional[float]
    high_pass: Optional[float]

    @classmethod
    @abstractmethod
    def from_ds(cls: Type[OpticalFilterType], ds: Dataset) -> OpticalFilterType:
        raise NotImplementedError()

    def insert_into_ds(self, ds: Dataset) -> Dataset:
        """Codes and insert object into dataset.

        Parameters
        ----------
        ds: Dataset
           Optical path sequence item.

        Returns
        ----------
        Dataset
            Dataset with object inserted.

        """
        if self.nominal is not None:
            ds.LightPathFilterPassBand = self.nominal
        if self.low_pass is not None and self.high_pass is not None:
            ds.LightPathFilterPassThroughwavelength = [self.low_pass, self.high_pass]
        if self.filters is not None:
            for filter in self.filters:
                ds = filter.insert_into_ds(ds)
        return ds


class LightPathFilter(OpticalFilter[LightPathFilterCode]):
    """Set of light path filter conditions for optical path"""

    @classmethod
    def from_ds(cls, ds: Dataset) -> "LightPathFilter":
        """Returns LightPathFilter object read from dataset
        (optical path sequence item).

        Parameters
        ----------
        ds: Dataset
           Optical path sequence item.

        Returns
        ----------
        LightPathFilter
            Object containing light path filter conditions for optical path.

        """
        filter_band = getattr(ds, "LightPathFilterPassBand", [None, None])
        return cls(
            filters=LightPathFilterCode.from_ds(ds),
            nominal=getattr(ds, "LightPathFilterPassThroughwavelengthh", None),
            low_pass=filter_band[0],
            high_pass=filter_band[1],
        )


@dataclass
class ImagePathFilter(OpticalFilter[ImagePathFilterCode]):
    """Set of image path filter conditions for optical path"""

    @classmethod
    def from_ds(cls, ds: Dataset) -> "ImagePathFilter":
        """Returns ImagePathFilter object read from dataset
        (optical path sequence item).

        Parameters
        ----------
        ds: Dataset
           Optical path sequence item.

        Returns
        ----------
        ImagePathFilter
            Object containing image path filter conditions for optical path.

        """
        filter_band = getattr(ds, "ImagePathFilterPassBand", [None, None])
        return cls(
            filters=ImagePathFilterCode.from_ds(ds),
            nominal=getattr(ds, "ImagePathFilterPassThroughwavelengthh", None),
            low_pass=filter_band[0],
            high_pass=filter_band[1],
        )


@dataclass
class Lenses:
    """Set of lens conditions for optical path"""

    lenses: Iterable[LenseCode] = field(default_factory=list)
    condenser_power: Optional[float] = None
    objective_power: Optional[float] = None
    objective_na: Optional[float] = None

    @classmethod
    def from_ds(cls, ds: Dataset) -> "Lenses":
        """Returns Lenses object read from dataset (optical path sequence
        item).

        Parameters
        ----------
        ds: Dataset
           Optical path sequence item.

        Returns
        ----------
        Lenses
            Object containing lense conditions for optical path.

        """
        return cls(
            lenses=LenseCode.from_ds(ds),
            condenser_power=getattr(ds, "CondenserLensPower", None),
            objective_power=getattr(ds, "ObjectiveLensPower", None),
            objective_na=getattr(ds, "ObjectiveLensNumericalAperture", None),
        )

    def insert_into_ds(self, ds: Dataset) -> Dataset:
        """Codes and insert object into dataset.

        Parameters
        ----------
        ds: Dataset
           Optical path sequence item.

        Returns
        ----------
        Dataset
            Dataset with object inserted.

        """
        if self.condenser_power is not None:
            ds.CondenserLensPower = self.condenser_power
        if self.objective_power is not None:
            ds.ObjectiveLensPower = self.objective_power
        if self.objective_na is not None:
            ds.ObjectiveLensNumericalAperture = self.objective_na
        if self.lenses is not None:
            for lense in self.lenses:
                ds = lense.insert_into_ds(ds)
        return ds


@dataclass
class OpticalPath(ModelBase):
    """
    Optical path metadata.

    Corresponds to the `Required`, `Required, Empty if Unknown`, and selected
    `Optional` attributes for an Optical Path Sequence item in the Optical Path Module:
    https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html
    """

    identifier: Optional[str] = None
    description: Optional[str] = None
    illumination_type: Optional[IlluminationCode] = None
    illumination: Optional[Union[float, IlluminationColorCode]] = None
    icc_profile: Optional[bytes] = None
    lut: Optional[Lut] = None
    light_path_filter: Optional[LightPathFilter] = None
    image_path_filter: Optional[ImagePathFilter] = None
    lenses: Optional[Lenses] = None
    overrides: Optional[Dict[str, bool]] = None

    def insert_into_dataset(self, dataset: Dataset, image_type: ImageType) -> None:
        if "OpticalPathSequence" not in dataset:
            dataset.OpticalPathSequence = DicomSequence()
        optical_path = Dataset()
        dicom_attributes: List[DicomAttribute] = [
            DicomStringAttribute(
                "OpticalPathIdentifier",
                True,
                self.identifier,
                lambda: self._generate_unique_identifier(dataset.OpticalPathSequence),
            ),
            DicomCodeAttribute(
                "IlluminationTypeCodeSequence",
                True,
                self.illumination_type.code
                if self.illumination_type is not None
                else None,
                IlluminationCode("Brightfield illumination").code,
            ),
            DicomStringAttribute("OpticalPathDescription", False, self.description),
            DicomByteAttribute(
                "ICCProfile",
                True,
                self.icc_profile,
            ),
        ]
        if self.lenses is not None:
            dicom_attributes.extend(
                # TODO check dicom tags for these, add lenses.
                (
                    DicomNumberAttribute(
                        "ObjectiveLensPower", False, self.lenses.objective_power
                    ),
                    DicomNumberAttribute(
                        "CondenserLensPower", False, self.lenses.condenser_power
                    ),
                    DicomNumberAttribute(
                        "ObjectiveNa", False, self.lenses.objective_na
                    ),
                )
            )
        if isinstance(self.illumination, float):
            dicom_attributes.append(
                DicomNumberAttribute("IlluminationWaveLength", True, self.illumination)
            )
        else:
            dicom_attributes.append(
                DicomCodeAttribute(
                    "IlluminationColorCodeSequence",
                    True,
                    self.illumination.code if self.illumination is not None else None,
                    IlluminationColorCode("Full Spectrum").code,
                )
            )
        self._insert_dicom_attributes_into_dataset(optical_path, dicom_attributes)
        dataset.OpticalPathSequence.append(optical_path)

    @staticmethod
    def _generate_unique_identifier(optical_paths: DicomSequence) -> str:
        identifiers = [
            optical_path.OpticalPathIdentifier for optical_path in optical_paths
        ]
        identifier = 0
        while identifier in identifiers:
            identifier += 1
        return str(identifier)
