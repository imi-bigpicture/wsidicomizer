import numpy as np
import pytest


from wsidicomizer.metadata.optical_path import (
    ConstantLutSegment,
    DiscreteLutSegment,
    LinearLutSegment,
    Lut,
)


class TestDicomLut:
    @pytest.mark.parametrize(
        ["lut", "expected_table_component"],
        [
            (
                Lut(
                    [ConstantLutSegment(0, 256)],
                    [ConstantLutSegment(0, 256)],
                    [LinearLutSegment(0, 255, 256)],
                    np.dtype(np.uint16),
                ),
                [
                    np.full(256, 0, dtype=np.uint16),
                    np.full(256, 0, dtype=np.uint16),
                    np.linspace(0, 255, 256, dtype=np.uint16),
                ],
            ),
            (
                Lut(
                    [ConstantLutSegment(0, 256)],
                    [ConstantLutSegment(0, 256)],
                    [
                        ConstantLutSegment(0, 100),
                        LinearLutSegment(0, 255, 100),
                        ConstantLutSegment(255, 56),
                    ],
                    np.dtype(np.uint16),
                ),
                [
                    np.full(256, 0, dtype=np.uint16),
                    np.full(256, 0, dtype=np.uint16),
                    np.concatenate(
                        [
                            np.full(100, 0, dtype=np.uint16),
                            np.linspace(0, 255, 100, dtype=np.uint16),
                            np.full(56, 255, dtype=np.uint16),
                        ]
                    ),
                ],
            ),
        ],
    )
    def test_parse_to_table(self, lut: Lut, expected_table_component: np.ndarray):
        # Arrange

        # Act
        table = lut.table

        # Assert
        for component, expected_component in zip(table, expected_table_component):
            assert len(component) == len(expected_component)
            assert np.array_equal(component, expected_component)
