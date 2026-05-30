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

import pytest
from pydicom.uid import UID
from wsidicom.metadata import (
    CallableUidGenerator,
    Equipment,
    Image,
    Label,
    Patient,
    Pyramid,
    Series,
    Slide,
    Study,
    WsiMetadata,
)
from wsidicom.metadata.sample import SlideSample

from wsidicomizer import MetadataUidResolver


# Each entity of the metadata fixture is its own fixture, defaulting to an
# unresolved value. The `empty_` prefix avoids shadowing the populated entity
# fixtures elsewhere. A test overrides any of them by parametrizing the fixture
# directly, e.g. `@pytest.mark.parametrize("empty_study", [Study(uid=UID(...))])`.


@pytest.fixture
def empty_study() -> Study:
    return Study()


@pytest.fixture
def empty_series() -> Series:
    return Series()


@pytest.fixture
def empty_patient() -> Patient:
    return Patient()


@pytest.fixture
def empty_equipment() -> Equipment:
    return Equipment()


@pytest.fixture
def empty_slide() -> Slide:
    return Slide(samples=[SlideSample(identifier="s1")])


@pytest.fixture
def empty_pyramid() -> Pyramid:
    return Pyramid(image=Image(), optical_paths=[])


@pytest.fixture
def empty_label() -> Label:
    return Label()


@pytest.fixture
def empty_frame_of_reference_uid() -> UID | None:
    return None


@pytest.fixture
def metadata(
    empty_study: Study,
    empty_series: Series,
    empty_patient: Patient,
    empty_equipment: Equipment,
    empty_slide: Slide,
    empty_pyramid: Pyramid,
    empty_label: Label,
    empty_frame_of_reference_uid: UID | None,
) -> WsiMetadata:
    return WsiMetadata(
        study=empty_study,
        series=empty_series,
        patient=empty_patient,
        equipment=empty_equipment,
        slide=empty_slide,
        pyramid=empty_pyramid,
        label=empty_label,
        frame_of_reference_uid=empty_frame_of_reference_uid,
    )


class _CounterUidGenerator:
    """Helper: generates UIDs of the form 1.2.3.<n>, counting each call."""

    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> UID:
        self.n += 1
        return UID(f"1.2.3.{self.n}")


@pytest.mark.unittest
class TestMetadataUidResolver:
    def test_resolves_all_unresolved_uids(self, metadata: WsiMetadata):
        # Arrange
        counter = _CounterUidGenerator()
        resolver = MetadataUidResolver(CallableUidGenerator(counter))

        # Act
        resolved = resolver.resolve(metadata)

        # Assert
        assert resolved.study.uid == "1.2.3.1"
        assert resolved.series.uid == "1.2.3.2"
        assert resolved.slide.samples is not None
        assert resolved.slide.samples[0].uid == "1.2.3.3"
        assert resolved.pyramid.uid == "1.2.3.4"
        assert resolved.frame_of_reference_uid == "1.2.3.5"
        assert resolved.dimension_organization_uids == [UID("1.2.3.6")]
        assert counter.n == 6

    @pytest.mark.parametrize("empty_study", [Study(uid=UID("5.5.5.5"))])
    @pytest.mark.parametrize("empty_frame_of_reference_uid", [UID("6.6.6.6")])
    def test_preserves_already_set_uids(self, metadata: WsiMetadata):
        # Arrange
        counter = _CounterUidGenerator()
        resolver = MetadataUidResolver(CallableUidGenerator(counter))

        # Act
        resolved = resolver.resolve(metadata)

        # Assert
        assert resolved.study.uid == "5.5.5.5"
        assert resolved.frame_of_reference_uid == "6.6.6.6"
        assert resolved.series.uid == "1.2.3.1"
        assert resolved.slide.samples is not None
        assert resolved.slide.samples[0].uid == "1.2.3.2"
        assert resolved.pyramid.uid == "1.2.3.3"
        assert resolved.dimension_organization_uids == [UID("1.2.3.4")]
        assert counter.n == 4

    def test_does_not_mutate_original(self, metadata: WsiMetadata):
        # Arrange
        resolver = MetadataUidResolver(CallableUidGenerator(_CounterUidGenerator()))

        # Act
        resolver.resolve(metadata)

        # Assert
        assert metadata.study.uid is None
        assert metadata.frame_of_reference_uid is None

    @pytest.mark.parametrize(
        "empty_slide",
        [Slide(samples=[SlideSample(identifier="s1", uid=UID("4.4.4.4"))])],
    )
    def test_preserves_already_set_sample_uid(self, metadata: WsiMetadata):
        # Arrange
        resolver = MetadataUidResolver(CallableUidGenerator(_CounterUidGenerator()))

        # Act
        resolved = resolver.resolve(metadata)

        # Assert
        assert resolved.slide.samples is not None
        assert resolved.slide.samples[0].uid == "4.4.4.4"
