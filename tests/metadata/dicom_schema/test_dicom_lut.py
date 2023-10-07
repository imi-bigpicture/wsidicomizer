import io
import numpy as np
from typing import Sequence, Tuple
from pydicom import Dataset
import pytest
from wsidicomizer.metadata.dicom_schema.optical_path import (
    LutDicomParser,
    LutDicomFormatter,
)

from wsidicomizer.metadata.optical_path import (
    ConstantLutSegment,
    DiscreteLutSegment,
    LinearLutSegment,
    Lut,
    LutSegment,
)


class TestDicomLut:
    @pytest.mark.parametrize(
        [
            "descriptor",
            "red_lut",
            "green_lut",
            "blue_lut",
            "expected",
        ],
        [
            (
                (256, 0, 8),
                b"\x00\x00\x01\x00\x00\x00\x01\x00\xff\x00\x00\x00",
                b"\x00\x00\x01\x00\x00\x00\x01\x00\xff\x00\x00\x00",
                b"\x00\x00\x01\x00\x00\x00\x01\x00\xff\x00\xff\x00",
                Lut(
                    [ConstantLutSegment(0, 256)],
                    [ConstantLutSegment(0, 256)],
                    [LinearLutSegment(0, 255, 256)],
                    np.dtype(np.uint8),
                ),
            ),
            (
                (256, 0, 16),
                b"\x01\x00\x00\x01\xff\xff",
                b"\x01\x00\x00\x01\x00\x00",
                b"\x01\x00\x00\x01\x00\x00",
                Lut(
                    [LinearLutSegment(0, 65535, 256)],
                    [ConstantLutSegment(0, 256)],
                    [ConstantLutSegment(0, 256)],
                    np.dtype(np.uint16),
                ),
            ),
        ],
    )
    def test_from_dataset(
        self,
        descriptor: Tuple[int, int, int],
        red_lut: bytes,
        green_lut: bytes,
        blue_lut: bytes,
        expected: Lut,
    ):
        # Arrange
        lut_dataset = Dataset()
        lut_dataset.RedPaletteColorLookupTableDescriptor = descriptor
        lut_dataset.GreenPaletteColorLookupTableDescriptor = descriptor
        lut_dataset.BluePaletteColorLookupTableDescriptor = descriptor
        lut_dataset.SegmentedRedPaletteColorLookupTableData = red_lut
        lut_dataset.SegmentedGreenPaletteColorLookupTableData = green_lut
        lut_dataset.SegmentedBluePaletteColorLookupTableData = blue_lut
        dataset = Dataset()
        dataset.PaletteColorLookupTableSequence = [lut_dataset]

        # Act
        lut = LutDicomParser.from_dataset(dataset)

        # Assert
        assert lut == expected

    @pytest.mark.parametrize(
        ["segment_data", "expected_segments"],
        [
            (
                b"\x00\x00\x01\x00\x00\x00\x01\x00\xff\x00\x00\x00",
                [ConstantLutSegment(0, 256)],
            ),
            (
                b"\x00\x00\x01\x00\x00\x00\x01\x00\xff\x00\xff\x00",
                [LinearLutSegment(0, 255, 256)],
            ),
        ],
    )
    def test_parse_segments(
        self, segment_data: bytes, expected_segments: Sequence[LutSegment]
    ):
        # Arrange

        # Act
        parsed = LutDicomParser._parse_segments(segment_data, np.dtype(np.uint16))

        # Assert
        assert list(parsed) == expected_segments

    @pytest.mark.parametrize(
        [
            "lut",
            "expected_descriptor",
            "expected_red_lut",
            "expected_green_lut",
            "expected_blue_lut",
        ],
        [
            (
                Lut(
                    [ConstantLutSegment(0, 256)],
                    [ConstantLutSegment(0, 256)],
                    [LinearLutSegment(0, 255, 256)],
                    np.dtype(np.uint8),
                ),
                (256, 0, 8),
                b"\x00\x01\x00\x01\xff\x00",
                b"\x00\x01\x00\x01\xff\x00",
                b"\x00\x01\x00\x01\xff\xff",
            ),
            (
                Lut(
                    [LinearLutSegment(0, 65535, 256)],
                    [ConstantLutSegment(0, 256)],
                    [ConstantLutSegment(0, 256)],
                    np.dtype(np.uint16),
                ),
                (256, 0, 16),
                b"\x00\x00\x01\x00\x00\x00\x01\x00\xff\x00\xff\xff",
                b"\x00\x00\x01\x00\x00\x00\x01\x00\xff\x00\x00\x00",
                b"\x00\x00\x01\x00\x00\x00\x01\x00\xff\x00\x00\x00",
            ),
        ],
    )
    def test_to_dataset(
        self,
        lut: Lut,
        expected_descriptor: Tuple[int, int, int],
        expected_red_lut: bytes,
        expected_green_lut: bytes,
        expected_blue_lut: bytes,
    ):
        # Arrange

        # Act
        dataset = LutDicomFormatter.to_dataset(lut)

        # Assert
        assert "PaletteColorLookupTableSequence" in dataset
        assert len(dataset.PaletteColorLookupTableSequence) == 1
        lut_dataset = dataset.PaletteColorLookupTableSequence[0]
        assert isinstance(lut_dataset, Dataset)
        assert lut_dataset.RedPaletteColorLookupTableDescriptor == expected_descriptor
        assert lut_dataset.GreenPaletteColorLookupTableDescriptor == expected_descriptor
        assert lut_dataset.BluePaletteColorLookupTableDescriptor == expected_descriptor
        assert lut_dataset.RedPaletteColorLookupTableData == expected_red_lut
        assert lut_dataset.GreenPaletteColorLookupTableData == expected_green_lut
        assert lut_dataset.BluePaletteColorLookupTableData == expected_blue_lut

    @pytest.mark.parametrize(
        ["given_data_type", "data", "expected_data_type"],
        [
            (np.dtype(np.uint8), b"\x00\x01", np.dtype(np.uint8)),
            (np.dtype(np.uint16), b"\x00\x01", np.dtype(np.uint8)),
            (np.dtype(np.uint8), b"\x00\x00\x01\x00", np.dtype(np.uint16)),
            (np.dtype(np.uint16), b"\x00\x00\x01\x00", np.dtype(np.uint16)),
        ],
    )
    def test_determine_correct_data_type(
        self, given_data_type: np.dtype, data: bytes, expected_data_type: np.dtype
    ):
        # Arrange

        # Act
        with io.BytesIO(data) as buffer:
            determined_data_type = LutDicomParser._determine_correct_data_type(
                buffer, given_data_type
            )

        # Assert
        assert determined_data_type == expected_data_type
