from enum import Enum
import io
import struct
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Type

import numpy as np
from marshmallow import fields, post_load, pre_dump
from pydicom import Dataset
from pydicom.sr.coding import Code
from wsidicom.conceptcode import (
    IlluminationCode,
    IlluminationColorCode,
    ImagePathFilterCode,
    LenseCode,
    LightPathFilterCode,
)

from wsidicomizer.metadata.defaults import Defaults
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema, LoadType
from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    CodeDicomField,
    DefaultingDicomField,
    FlatteningNestedField,
    FloatDicomField,
    SingleCodeDicomField,
)
from wsidicomizer.metadata.optical_path import (
    ConstantLutSegment,
    DiscreteLutSegment,
    ImagePathFilter,
    LightPathFilter,
    LinearLutSegment,
    Lut,
    LutSegment,
    Objectives,
    OpticalFilter,
    OpticalPath,
)


class LutSegmentType(Enum):
    DISCRETE = 0
    LINEAR = 1
    INDIRECT = 2


class LutDicomParser:
    @classmethod
    def from_dataset(cls, dataset: Dataset) -> Optional[Lut]:
        """Read LUT from a DICOM optical path dataset..

        Parameters
        ----------
        dataset: Dataset
            Optical path dataset with LUT to parse.

        """
        if (
            not "PaletteColorLookupTableSequence" in dataset
            or len(dataset.PaletteColorLookupTableSequence) == 0
        ):
            return None
        lut_dataset = dataset.PaletteColorLookupTableSequence[0]
        length, first, bits = lut_dataset.RedPaletteColorLookupTableDescriptor
        bits = bits
        if bits == 8:
            data_type = np.dtype(np.uint8)
        else:
            data_type = np.dtype(np.uint16)

        segmented_keys = (
            "SegmentedRedPaletteColorLookupTableData",
            "SegmentedGreenPaletteColorLookupTableData",
            "SegmentedBluePaletteColorLookupTableData",
        )
        non_segmented_keys = (
            "RedPaletteColorLookupTableData",
            "GreenPaletteColorLookupTableData",
            "BluePaletteColorLookupTableData",
        )
        if all(key in lut_dataset for key in segmented_keys):
            red = list(
                cls._parse_segments(
                    lut_dataset.SegmentedRedPaletteColorLookupTableData, data_type
                )
            )
            green = list(
                cls._parse_segments(
                    lut_dataset.SegmentedGreenPaletteColorLookupTableData, data_type
                )
            )
            blue = list(
                cls._parse_segments(
                    lut_dataset.SegmentedBluePaletteColorLookupTableData, data_type
                )
            )

        elif all(key in lut_dataset for key in non_segmented_keys):
            red = [
                cls._parse_single_discrete_segment(
                    lut_dataset.RedPaletteColorLookupTableData, data_type
                )
            ]
            green = [
                cls._parse_single_discrete_segment(
                    lut_dataset.GreenPaletteColorLookupTableData, data_type
                )
            ]
            blue = [
                cls._parse_single_discrete_segment(
                    lut_dataset.BluePaletteColorLookupTableData, data_type
                )
            ]
        else:
            raise ValueError(
                "Lookup table data or segmented lookup table data missing for one "
                "or more components."
            )
        for color in (red, green, blue):
            cls._add_start_and_end(first, length, color)
        return Lut(
            red=red,
            green=green,
            blue=blue,
            data_type=data_type,
        )

    @classmethod
    def _parse_segments(
        cls, segmented_lut_data: bytes, data_type: np.dtype
    ) -> Iterator[LutSegment]:
        """Parse segments from segmented lut data."""
        previous_segment_type: Optional[LutSegmentType] = None
        previous_segment_end_value: Optional[int] = None
        with io.BytesIO(segmented_lut_data) as buffer:
            data_type = cls._determine_correct_data_type(buffer, data_type)
            next_segment_type = cls._read_next_segment_type(buffer, data_type)
            while next_segment_type != None:
                segment_type = next_segment_type
                if segment_type == LutSegmentType.DISCRETE:
                    length = cls._read_value(buffer, data_type)
                    values = cls._read_values(buffer, length, data_type)
                    next_segment_type = cls._read_next_segment_type(buffer, data_type)
                    if next_segment_type == LutSegmentType.LINEAR:
                        # If next segment is linear it will take over the last value.
                        previous_segment_end_value = values.pop()
                    if len(values) > 0:
                        yield DiscreteLutSegment(values)
                    previous_segment_type = segment_type

                elif segment_type == LutSegmentType.LINEAR:
                    length = cls._read_value(buffer, data_type)
                    end_value = cls._read_value(buffer, data_type)
                    if previous_segment_end_value is not None:
                        start_value = previous_segment_end_value
                        if previous_segment_type == LutSegmentType.DISCRETE:
                            # If the previous segment was discrete, this segment
                            # takes over its last value.
                            length += 1
                    else:
                        # The standard does allow the first segment to be a linear
                        # segment, but if it happens it is likely that the first value
                        # should be 0
                        start_value = 0
                    if start_value == end_value:
                        yield ConstantLutSegment(start_value, length)
                    else:
                        yield LinearLutSegment(start_value, end_value, length)
                    previous_segment_type = segment_type
                    next_segment_type = cls._read_next_segment_type(buffer, data_type)
                    previous_segment_end_value = end_value
                elif segment_type == LutSegmentType.INDIRECT:
                    raise NotImplementedError(
                        "Indirect segment types are not implemented."
                    )
                else:
                    raise ValueError("Unknown segment type.")

    @classmethod
    def _add_start_and_end(
        cls, start_length: int, total_length: int, segments: List[LutSegment]
    ):
        """Add start and end constant segments if needed."""
        start_segment = cls._create_start_segment(start_length, segments)
        end_segment = cls._create_end_segment(start_length, total_length, segments)
        if start_segment is not None:
            segments.insert(0, start_segment)
        if end_segment is not None:
            segments.append(end_segment)

    @staticmethod
    def _create_start_segment(
        start_length: int, segments: Sequence[LutSegment]
    ) -> Optional[ConstantLutSegment]:
        """Create a start segment if needed."""
        if start_length == 0:
            return None
        first_segment = segments[0]
        if isinstance(first_segment, ConstantLutSegment):
            first_segment.length += start_length
            return None
        if isinstance(first_segment, DiscreteLutSegment):
            start_value = first_segment.values[0]
        elif isinstance(first_segment, LinearLutSegment):
            start_value = first_segment.start_value
        else:
            raise ValueError("Unknown segment type.")
        return ConstantLutSegment(start_value, start_length)

    @staticmethod
    def _create_end_segment(
        start_length, total_length: int, segments: Sequence[LutSegment]
    ):
        """Create a end segment if needed."""
        length = start_length
        last_segment = segments[-1]
        length = sum(len(segment) for segment in segments)
        segment_length = total_length - length
        if segment_length < 0:
            raise ValueError("Got a negative length for last segment.")
        if segment_length == 0:
            return None
        if isinstance(last_segment, ConstantLutSegment):
            last_segment.length += segment_length
            return None
        if isinstance(last_segment, DiscreteLutSegment):
            end_value = last_segment.values[-1]
        elif isinstance(last_segment, LinearLutSegment):
            end_value = last_segment.end_value
        else:
            raise ValueError("Unknown segment type.")
        return ConstantLutSegment(end_value, segment_length)

    @classmethod
    def _read_next_segment_type(
        cls, buffer: io.BytesIO, data_type: np.dtype
    ) -> Optional[LutSegmentType]:
        """
        Read next segment type from buffer.

        Return None if not enough data left to read.
        """
        try:
            return LutSegmentType(cls._read_value(buffer, data_type))
        except struct.error:
            return None

    @staticmethod
    def _read_value(buffer: io.BytesIO, data_type: np.dtype) -> int:
        """Read a single value from buffer."""
        if data_type == np.dtype(np.uint8):
            format = "<B"
        else:
            format = "<H"
        return struct.unpack(format, buffer.read(data_type.itemsize))[0]

    @staticmethod
    def _read_values(buffer: io.BytesIO, count: int, data_type: np.dtype) -> List[int]:
        """Read multiple values from buffer."""
        if data_type == np.dtype(np.uint8):
            format = f'<{count*"B"}'
        else:
            format = f'<{count*"H"}'
        return list(struct.unpack(format, buffer.read(data_type.itemsize * count)))

    @classmethod
    def _parse_single_discrete_segment(
        cls, segment_data: bytes, data_type: np.dtype
    ) -> DiscreteLutSegment:
        """Read discrete segment from data."""
        length = len(segment_data) // data_type.itemsize
        if data_type == np.dtype(np.uint8):
            format = f'<{length*"B"}'
        else:
            format = f'<{length*"H"}'
        values = list(struct.unpack(format, segment_data))
        return DiscreteLutSegment(values)

    @classmethod
    def _determine_correct_data_type(
        cls, buffer: io.BytesIO, data_type: np.dtype
    ) -> np.dtype:
        """Determine correct data type for reading segment.

        The segment can either have 8- or 16-bits values. The first value indicates the
        segment type and should be 0, 1, or 2. The second value indicates a length that
        should be larger than 0.

        If reading 8 bits values as 16 bits the segment type will not be 0, 1, or 2, as
        the length value is also read. Then re-try reading as 8 bits.

        If reading 16 bit values as 8 bits the segment length will not be larger than 0,
        as the read value is the second half of the segment type value. Then re-try
        reading as 16 bits.
        """
        buffer.seek(0)
        try:
            cls._read_next_segment_type(buffer, data_type)
        except ValueError as exception:
            # Throws if first read data is not a valid segment type (0, 1, or 2.)
            if data_type == np.dtype(np.uint16):
                # Try reading the segment type as 8 bits
                return cls._determine_correct_data_type(buffer, np.dtype(np.uint8))
            raise ValueError("Failed to parse first segment type from data", exception)

        length = cls._read_value(buffer, data_type)
        if length > 0:
            # Length should be positive for all segment types
            buffer.seek(0)
            return data_type
        if data_type == np.dtype(np.uint8):
            # Try reading the segment as 16 bits.
            return cls._determine_correct_data_type(buffer, np.dtype(np.uint16))
        raise ValueError("Failed to parse first segment length from data.")


class LutDicomFormatter:
    @classmethod
    def to_dataset(cls, lut: Lut) -> Dataset:
        """Convert lut into dataset."""
        lut_dataset = Dataset()
        start = cls._find_common_start(lut)
        end = cls._find_common_end(lut)
        if start is None:
            start = 0
        if lut.length == 2**16:
            length = 0
        else:
            length = lut.length
        descriptor = (length, start, lut.bits)
        lut_dataset.RedPaletteColorLookupTableDescriptor = descriptor
        lut_dataset.GreenPaletteColorLookupTableDescriptor = descriptor
        lut_dataset.BluePaletteColorLookupTableDescriptor = descriptor
        lut_dataset.RedPaletteColorLookupTableData = cls._pack_segments(
            lut.red, lut.data_type, start, end
        )
        lut_dataset.GreenPaletteColorLookupTableData = cls._pack_segments(
            lut.green, lut.data_type, start, end
        )
        lut_dataset.BluePaletteColorLookupTableData = cls._pack_segments(
            lut.blue, lut.data_type, start, end
        )
        dataset = Dataset()
        dataset.PaletteColorLookupTableSequence = [lut_dataset]
        return dataset

    @classmethod
    def _find_common_start(cls, lut: Lut) -> Optional[int]:
        """Return constant start length (not necessary same value) across components."""
        first_segments = (lut.red[0], lut.green[0], lut.blue[0])
        return cls._find_common_constant_length(first_segments)

    @classmethod
    def _find_common_end(cls, lut: Lut) -> Optional[int]:
        """Return constant end length (not necessary same value) across components."""
        last_segments = (lut.red[-1], lut.green[-1], lut.blue[-1])
        return cls._find_common_constant_length(last_segments)

    @staticmethod
    def _find_common_constant_length(segments: Sequence[LutSegment]) -> Optional[int]:
        """Return minumum constant length between components."""
        if not all(isinstance(segment, ConstantLutSegment) for segment in segments):
            return None
        return min(len(segment) for segment in segments)

    @classmethod
    def _pack_segments(
        cls,
        segments: Sequence[LutSegment],
        data_type: np.dtype,
        start: Optional[int],
        end: Optional[int],
    ) -> bytes:
        """Pack segments into bytes."""
        if data_type == np.dtype(np.uint8):
            data_format = "B"
        else:
            data_format = "H"
        previous_segment: Optional[LutSegment] = None
        end_index = len(segments) - 1
        with io.BytesIO() as buffer:
            for index, segment in enumerate(segments):
                if isinstance(segment, DiscreteLutSegment):
                    if index + 1 <= end_index:
                        next_segment = segments[index + 1]
                    else:
                        next_segment = None
                    cls._pack_discrete_segment(
                        buffer, segment, next_segment, data_format
                    )
                elif isinstance(segment, ConstantLutSegment):
                    cls._pack_constant_segment(
                        buffer,
                        segment,
                        previous_segment,
                        index,
                        end_index,
                        start,
                        end,
                        data_format,
                    )

                elif isinstance(segment, LinearLutSegment):
                    cls._pack_linear_segment(
                        buffer, segment, previous_segment, data_format
                    )
                else:
                    raise NotImplementedError()
                previous_segment = segment
            return buffer.getvalue()

    @classmethod
    def _pack_discrete_segment(
        cls,
        buffer: io.BytesIO,
        segment: DiscreteLutSegment,
        next_segment: Optional[LutSegment],
        data_format: str,
    ):
        values = list(segment.values)
        next_segment = next_segment
        if isinstance(next_segment, LinearLutSegment):
            values.append(next_segment.start_value)
        cls._pack_discrete_data(buffer, values, data_format)

    @classmethod
    def _pack_constant_segment(
        cls,
        buffer: io.BytesIO,
        segment: ConstantLutSegment,
        previous_segment: Optional[LutSegment],
        index: int,
        end_index: int,
        start: Optional[int],
        end: Optional[int],
        data_format: str,
    ):
        length = segment.length
        if start is not None and index == 0:
            length = segment.length - start
        elif end is not None and index == end_index:
            length = segment.length - end
        if not isinstance(previous_segment, DiscreteLutSegment):
            cls._pack_discrete_data(
                buffer,
                [segment.value],
                data_format,
            )
        cls._pack_linear_data(buffer, length - 1, segment.value, data_format)

    @classmethod
    def _pack_linear_segment(
        cls,
        buffer: io.BytesIO,
        segment: LinearLutSegment,
        previous_segment: Optional[LutSegment],
        data_format: str,
    ):
        if not isinstance(previous_segment, DiscreteLutSegment):
            cls._pack_discrete_data(
                buffer,
                [segment.start_value],
                data_format,
            )
        cls._pack_linear_data(
            buffer, segment.length - 1, segment.end_value, data_format
        )

    @staticmethod
    def _pack_discrete_data(
        buffer: io.BytesIO,
        values: Sequence[int],
        data_format: str,
    ):
        """Pack discrete segment to buffer."""
        buffer.write(
            struct.pack(
                "<" + 2 * data_format,
                LutSegmentType.DISCRETE.value,
                len(values),
            )
        )
        for value in values:
            buffer.write(struct.pack("<" + data_format, value))

    @staticmethod
    def _pack_linear_data(
        buffer: io.BytesIO,
        length: int,
        end_value: int,
        data_format: str,
    ):
        """Pack linear segment to buffer."""
        buffer.write(
            struct.pack(
                "<" + 3 * data_format,
                LutSegmentType.LINEAR.value,
                length,
                end_value,
            )
        )


class FilterDicomSchema(DicomSchema[LoadType]):
    @pre_dump
    def pre_dump(self, filter: OpticalFilter, **kwargs):
        return {
            "filters": filter.filters,
            "nominal": filter.nominal,
            "filter_band": [filter.low_pass, filter.high_pass],
        }

    @post_load
    def post_load(self, data: Dict[str, Any], **kwargs):
        filter_band = data.pop("filter_band", None)
        if filter_band is not None:
            data["low_pass"] = filter_band[0]
            data["high_pass"] = filter_band[1]
        return super().post_load(data, **kwargs)


class LightPathFilterDicomSchema(FilterDicomSchema[LightPathFilter]):
    filters = fields.List(
        CodeDicomField(LightPathFilterCode),
        data_key="LightPathFilterTypeStackCodeSequence",
        allow_none=True,
    )
    nominal = fields.Integer(
        data_key="LightPathFilterPassThroughWavelength", allow_none=True
    )
    low_pass = fields.Integer(load_only=True, allow_none=True)
    high_pass = fields.Integer(load_only=True, allow_none=True)
    filter_band = fields.List(
        fields.Integer(),
        data_key="LightPathFilterPassBand",
    )

    @property
    def load_type(self) -> Type[LightPathFilter]:
        return LightPathFilter


class ImagePathFilterDicomSchema(FilterDicomSchema[ImagePathFilter]):
    filters = fields.List(
        CodeDicomField(ImagePathFilterCode),
        data_key="ImagePathFilterTypeStackCodeSequence",
        allow_none=True,
    )
    nominal = fields.Integer(
        data_key="ImagePathFilterPassThroughWavelength", allow_none=True
    )
    low_pass = fields.Integer(load_only=True, allow_none=True)
    high_pass = fields.Integer(load_only=True, allow_none=True)
    filter_band = fields.List(
        fields.Integer(),
        data_key="ImagePathFilterPassBand",
    )

    @property
    def load_type(self) -> Type[ImagePathFilter]:
        return ImagePathFilter


class ObjectivesSchema(DicomSchema[Objectives]):
    lenses = fields.List(
        CodeDicomField(LenseCode), data_key="LensesCodeSequence", allow_none=True
    )
    condenser_power = FloatDicomField(data_key="CondenserLensPower", allow_none=True)
    objective_power = FloatDicomField(data_key="ObjectiveLensPower", allow_none=True)
    objective_numerical_aperature = FloatDicomField(
        data_key="ObjectiveLensNumericalAperture", allow_none=True
    )

    @property
    def load_type(self) -> Type[Objectives]:
        return Objectives


class OpticalPathDicomSchema(DicomSchema[OpticalPath]):
    identifier = fields.String(data_key="OpticalPathIdentifier")
    description = fields.String(data_key="OpticalPathDescription")
    illumination_types = DefaultingDicomField(
        fields.List(CodeDicomField(IlluminationCode)),
        data_key="IlluminationTypeCodeSequence",
        dump_default=[Defaults.illumination_type],
    )
    illumination_wavelength = fields.Integer(
        data_key="IlluminationWaveLength", load_default=None
    )
    illumination_color_code = SingleCodeDicomField(
        IlluminationColorCode,
        data_key="IlluminationColorCodeSequence",
        load_default=None,
    )

    # icc_profile: Optional[bytes] = None
    light_path_filter = FlatteningNestedField(
        LightPathFilterDicomSchema(), load_default=None
    )
    image_path_filter = FlatteningNestedField(
        ImagePathFilterDicomSchema(), load_default=None
    )
    objective = FlatteningNestedField(ObjectivesSchema(), load_default=None)

    @property
    def load_type(self) -> Type[OpticalPath]:
        return OpticalPath

    @pre_dump
    def pre_dump(self, optical_path: OpticalPath, **kwargs):
        fields = {
            "identifier": optical_path.identifier,
            "description": optical_path.description,
            "illumination_types": optical_path.illumination_types,
            "light_path_filter": optical_path.light_path_filter,
            "image_path_filter": optical_path.image_path_filter,
            "objective": optical_path.objective,
        }

        if isinstance(optical_path.illumination, float):
            fields["illumination_wavelength"] = optical_path.illumination
        if isinstance(optical_path.illumination, Code):
            fields["illumination_color_code"] = optical_path.illumination
        else:
            fields["illumination_color_code"] = Defaults.illumination
        return fields

    @post_load
    def post_load(self, data: Dict[str, Any], **kwargs):
        illumination_wavelength = data.pop("illumination_wavelength", None)
        illumination_color_code = data.pop("illumination_color_code", None)
        if illumination_wavelength is not None:
            data["illumination"] = illumination_wavelength
        elif illumination_color_code is not None:
            data["illumination"] = illumination_color_code
        return super().post_load(data, **kwargs)
