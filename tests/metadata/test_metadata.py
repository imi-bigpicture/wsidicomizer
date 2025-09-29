#    Copyright 2023 SECTRA AB
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

from typing import Optional

import pytest
from pydicom.uid import UID
from wsidicom.metadata import (
    Equipment,
    Image,
    Label,
    OpticalPath,
    Patient,
    Pyramid,
    Series,
    Slide,
    Study,
    WsiMetadata,
)

from wsidicomizer.metadata import WsiDicomizerMetadata


@pytest.fixture
def base_equipment():
    yield Equipment("base", "base", None, None)


@pytest.fixture
def user_equipment():
    yield Equipment("user", None, None, None)


@pytest.fixture
def default_equipment():
    yield Equipment("default", "default", "default", None)


class TestWsiDicomizerMetadata:
    def test_merge_simple(
        self,
        base_equipment: Equipment,
        user_equipment: Equipment,
        default_equipment: Equipment,
    ):
        # Arrange

        # Act
        merged = WsiDicomizerMetadata._merge(
            Equipment, base_equipment, user_equipment, default_equipment
        )

        # Assert
        assert merged is not None
        assert merged.manufacturer == user_equipment.manufacturer
        assert merged.model_name == base_equipment.model_name
        assert merged.device_serial_number == default_equipment.device_serial_number
        assert merged.software_versions is None

    def test_merge_nested(
        self,
        base_equipment: Equipment,
        user_equipment: Equipment,
        default_equipment: Equipment,
        study: Study,
        series: Series,
        patient: Patient,
        icc_profile: bytes,
    ):
        base = WsiDicomizerMetadata(
            study=Study(),
            series=series,
            patient=Patient(),
            equipment=base_equipment,
            pyramid=Pyramid(
                image=Image(),
                optical_paths=[
                    OpticalPath(identifier="base 1"),
                    OpticalPath(identifier="base 2"),
                ],
            ),
            slide=Slide(),
            label=Label(),
        )
        user = WsiMetadata(
            study=study,
            series=Series(),
            patient=Patient(),
            equipment=user_equipment,
            pyramid=Pyramid(
                image=Image(),
                optical_paths=[
                    OpticalPath(description="user 1"),
                    OpticalPath(description="user 2"),
                ],
            ),
            slide=Slide(),
            label=Label(),
        )
        default = WsiMetadata(
            study=study,
            series=Series(),
            patient=patient,
            equipment=default_equipment,
            pyramid=Pyramid(
                image=Image(),
                optical_paths=[
                    OpticalPath(icc_profile=icc_profile),
                ],
            ),
            slide=Slide(),
            label=Label(),
        )

        # Act
        merged = base.merge(user, default, True)

        # Assert
        assert merged is not None
        assert merged.equipment is not None
        assert merged.equipment.manufacturer == user_equipment.manufacturer
        assert merged.equipment.model_name == base_equipment.model_name
        assert (
            merged.equipment.device_serial_number
            == default_equipment.device_serial_number
        )
        assert merged.equipment.software_versions is None
        assert merged.study == study
        assert merged.series == series
        assert merged.patient == patient
        assert len(merged.pyramid.optical_paths) == len(base.pyramid.optical_paths)
        assert (
            merged.pyramid.optical_paths[0].identifier
            == base.pyramid.optical_paths[0].identifier
        )
        assert (
            merged.pyramid.optical_paths[0].description
            == user.pyramid.optical_paths[0].description
        )
        assert (
            merged.pyramid.optical_paths[0].icc_profile
            == default.pyramid.optical_paths[0].icc_profile
        )
        assert (
            merged.pyramid.optical_paths[1].identifier
            == base.pyramid.optical_paths[1].identifier
        )
        assert (
            merged.pyramid.optical_paths[1].description
            == user.pyramid.optical_paths[1].description
        )
        assert (
            merged.pyramid.optical_paths[1].icc_profile
            == default.pyramid.optical_paths[0].icc_profile
        )

    @pytest.mark.parametrize(
        [
            "base_frame_of_reference_uid",
            "user_frame_of_reference_uid",
            "default_frame_of_reference_uid",
        ],
        [
            (UID("1.2.3"), UID("4.5.6"), UID("7.8.9")),
            (UID("1.2.3"), UID("4.5.6"), None),
            (UID("1.2.3"), None, UID("7.8.9")),
            (None, UID("4.5.6"), UID("7.8.9")),
            (UID("1.2.3"), None, None),
            (None, UID("4.5.6"), None),
            (None, None, UID("7.8.9")),
            (None, None, None),
        ],
    )
    def test_merge_frame_of_reference_uid(
        self,
        base_frame_of_reference_uid: Optional[UID],
        user_frame_of_reference_uid: Optional[UID],
        default_frame_of_reference_uid: Optional[UID],
    ):
        # Arrange
        base = WsiDicomizerMetadata(frame_of_reference_uid=base_frame_of_reference_uid)
        user = WsiDicomizerMetadata(frame_of_reference_uid=user_frame_of_reference_uid)
        default = WsiDicomizerMetadata(
            frame_of_reference_uid=default_frame_of_reference_uid
        )
        if user_frame_of_reference_uid:
            expected_frame_of_reference_uid = user_frame_of_reference_uid
        elif base_frame_of_reference_uid:
            expected_frame_of_reference_uid = base_frame_of_reference_uid
        elif default_frame_of_reference_uid:
            expected_frame_of_reference_uid = default_frame_of_reference_uid
        else:
            expected_frame_of_reference_uid = None

        # Act
        merged = base.merge(user, default, True)

        # Assert
        assert merged.frame_of_reference_uid == expected_frame_of_reference_uid

    @pytest.mark.parametrize(
        [
            "base_dimension_organization_uid",
            "user_dimension_organization_uid",
            "default_dimension_organization_uid",
        ],
        [
            (UID("1.2.3"), UID("4.5.6"), UID("7.8.9")),
            (UID("1.2.3"), UID("4.5.6"), None),
            (UID("1.2.3"), None, UID("7.8.9")),
            (None, UID("4.5.6"), UID("7.8.9")),
            (UID("1.2.3"), None, None),
            (None, UID("4.5.6"), None),
            (None, None, UID("7.8.9")),
            (None, None, None),
        ],
    )
    def test_merge_dimension_organization_uids(
        self,
        base_dimension_organization_uid: Optional[UID],
        user_dimension_organization_uid: Optional[UID],
        default_dimension_organization_uid: Optional[UID],
    ):
        # Arrange
        base = WsiDicomizerMetadata(
            dimension_organization_uids=(
                [base_dimension_organization_uid]
                if base_dimension_organization_uid
                else None
            )
        )
        user = WsiDicomizerMetadata(
            dimension_organization_uids=(
                [user_dimension_organization_uid]
                if user_dimension_organization_uid
                else None
            )
        )
        default = WsiDicomizerMetadata(
            dimension_organization_uids=(
                [default_dimension_organization_uid]
                if default_dimension_organization_uid
                else None
            )
        )
        if user_dimension_organization_uid:
            expected_dimension_organization_uid = [user_dimension_organization_uid]
        elif base_dimension_organization_uid:
            expected_dimension_organization_uid = [base_dimension_organization_uid]
        elif default_dimension_organization_uid:
            expected_dimension_organization_uid = [default_dimension_organization_uid]
        else:
            expected_dimension_organization_uid = None

        # Act
        merged = base.merge(user, default, True)

        # Assert
        assert merged.dimension_organization_uids == expected_dimension_organization_uid
