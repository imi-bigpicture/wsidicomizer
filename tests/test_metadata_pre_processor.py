#    Copyright 2026 SECTRA AB
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

"""Tests changing what a file says about itself before the merge."""

from dataclasses import replace
from typing import Any

import pytest
from decoy import Decoy
from upath import UPath
from wsidicom.metadata import Equipment, Label, Patient, Study

from wsidicomizer.dicomizer_source import DicomizerSource
from wsidicomizer.metadata import MetadataPreProcessor, WsiDicomizerMetadata


@pytest.fixture
def base_metadata() -> WsiDicomizerMetadata:
    return WsiDicomizerMetadata(
        study=Study(identifier="REAL-CASE"),
        patient=Patient(name="REAL PATIENT"),
        equipment=Equipment(
            manufacturer="Scanner Co",
            model_name="S-1000",
            software_versions=["1.2"],
            device_serial_number="SN-1234",
        ),
        label=Label(text="REAL LABEL"),
    )


class FakeSource(DicomizerSource):
    """A source that reads nothing but the metadata it is made with.

    Not a mock: the metadata of a source is what is under test here, so the
    behaviour of the class it is a source of is what has to run.
    """

    def __init__(self, base_metadata: WsiDicomizerMetadata, **kwargs):
        self._base_metadata = base_metadata
        super().__init__(filepath=UPath("slide.svs"), encoder=None, **kwargs)

    @staticmethod
    def is_supported(path, file_options: dict[str, Any] | None = None) -> bool:
        return True

    @property
    def base_metadata(self) -> WsiDicomizerMetadata:
        return self._base_metadata

    @property
    def _pixel_format(self):
        raise NotImplementedError()

    @property
    def pyramid_levels(self):
        raise NotImplementedError()

    def _create_level_image_data(self, level_index: int):
        raise NotImplementedError()

    def _create_label_image_data(self):
        raise NotImplementedError()

    def _create_overview_image_data(self):
        raise NotImplementedError()

    def _create_thumbnail_image_data(self):
        raise NotImplementedError()

    def close(self) -> None:
        pass


@pytest.fixture
def pre_processor(decoy: Decoy) -> MetadataPreProcessor:
    return decoy.mock(name="metadata_pre_processor")


@pytest.fixture
def user_metadata():
    return None


@pytest.fixture
def include_confidential() -> bool:
    return True


@pytest.fixture
def source(
    base_metadata: WsiDicomizerMetadata,
    user_metadata: WsiDicomizerMetadata | None,
    pre_processor: MetadataPreProcessor | None,
    include_confidential: bool,
):
    """A source of that file, made with what the test wants to give it."""
    return FakeSource(
        base_metadata,
        metadata=user_metadata,
        metadata_pre_processor=pre_processor,
        include_confidential=include_confidential,
    )


class TestMetadataPreProcessor:
    @pytest.mark.parametrize(
        (   "user_metadata", "pre_processor"),
        [
            (
                WsiDicomizerMetadata(
                    equipment=Equipment(manufacturer="Curated Co", model_name="S-1000")
                ),
                None,
            ),
        ],
    )
    @pytest.mark.parametrize("include_confidential", [True, False])
    def test_no_pre_processor_merge(
        self,
        source: DicomizerSource,
        base_metadata: WsiDicomizerMetadata,
        user_metadata: WsiDicomizerMetadata,
    ):
        # Arrange

        # Act
        written = source.metadata

        # Assert
        assert written.equipment.manufacturer == user_metadata.equipment.manufacturer
        assert written.equipment.model_name == base_metadata.equipment.model_name

    @pytest.mark.parametrize(
        ("user_metadata", "pre_processor"),
        [
            (
                WsiDicomizerMetadata(equipment=Equipment(manufacturer="Curated Co")),
                lambda base: replace(base, equipment=Equipment()),
            ),
        ],
    )
    @pytest.mark.parametrize("include_confidential", [True, False])
    def test_pre_processor_drops_part_followed_by_merge(
        self, source: DicomizerSource, user_metadata: WsiDicomizerMetadata
    ):
        # Act
        written = source.metadata

        # Assert
        assert written.equipment.manufacturer == user_metadata.equipment.manufacturer
        assert written.equipment.model_name is None
        assert written.equipment.software_versions is None

    @pytest.mark.parametrize(
        ("user_metadata", "pre_processor"),
        [
            (
                WsiDicomizerMetadata(study=Study(identifier="CURATED-CASE")),
                lambda base: WsiDicomizerMetadata(),
            ),
        ],
    )
    def test_pre_processor_drops_all_followed_by_merge(
        self, source: DicomizerSource, user_metadata: WsiDicomizerMetadata
    ):
        # Arrange

        # Act
        written = source.metadata

        # Assert: what the caller passed is merged in regardless.
        assert written.study.identifier == user_metadata.study.identifier
        assert written.equipment.manufacturer is None

    @pytest.mark.parametrize("include_confidential", [False])
    def test_pre_processor_does_not_see_base_confidential_metadata(
        self,
        decoy: Decoy,
        base_metadata: WsiDicomizerMetadata,
        source: DicomizerSource,
        pre_processor: MetadataPreProcessor,
    ):
        # Arrange
        seen: list[WsiDicomizerMetadata | None] = []

        def record(base: WsiDicomizerMetadata) -> WsiDicomizerMetadata:
            nonlocal seen
            seen.append(base)
            return base

        metadata_without_confidential = base_metadata.remove_confidential()
        decoy.when(pre_processor(metadata_without_confidential)).then_do(record)

        # Act
        _ = source.metadata

        # Assert
        assert len(seen) == 1
        assert seen[0] == metadata_without_confidential

    @pytest.mark.parametrize("include_confidential", [True])
    def test_pre_processor_sees_base_confidential_metadata(
        self,
        decoy: Decoy,
        base_metadata: WsiDicomizerMetadata,
        source: DicomizerSource,
        pre_processor: MetadataPreProcessor,
    ):
        seen: list[WsiDicomizerMetadata | None] = []

        def record(base: WsiDicomizerMetadata) -> WsiDicomizerMetadata:
            nonlocal seen
            seen.append(base)
            return base

        decoy.when(pre_processor(base_metadata)).then_do(record)

        # Act
        _ = source.metadata

        # Assert
        assert len(seen) == 1
        assert seen[0] == base_metadata
