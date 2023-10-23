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

"""Base model for metadata."""
from dataclasses import fields, is_dataclass
from typing import Any, Optional, Sequence, Type, TypeVar

from pydicom.uid import UID
from wsidicom.metadata import (
    Equipment,
    Image,
    Label,
    OpticalPath,
    Patient,
    Series,
    Slide,
    Study,
    WsiMetadata,
)

ModelType = TypeVar("ModelType")


class WsiDicomizerMetadata(WsiMetadata):
    """Subclass of WsiMetadata that can be constructed with optional parameters."""

    def __init__(
        self,
        study: Optional[Study] = None,
        series: Optional[Series] = None,
        patient: Optional[Patient] = None,
        equipment: Optional[Equipment] = None,
        optical_paths: Optional[Sequence[OpticalPath]] = None,
        slide: Optional[Slide] = None,
        label: Optional[Label] = None,
        image: Optional[Image] = None,
        frame_of_reference_uid: Optional[UID] = None,
        dimension_organization_uids: Optional[Sequence[UID]] = None,
    ):
        super().__init__(
            study if study is not None else Study(),
            series if series is not None else Series(),
            patient if patient is not None else Patient(),
            equipment if equipment is not None else Equipment(),
            optical_paths if optical_paths is not None else [],
            slide if slide is not None else Slide(),
            label if label is not None else Label(),
            image if image is not None else Image(),
            frame_of_reference_uid,
            dimension_organization_uids,
        )

    def merge(
        self,
        user: Optional[WsiMetadata],
        default: Optional[WsiMetadata],
        include_confidential: bool,
    ) -> WsiMetadata:
        if not include_confidential:
            base = self._remove_confidential()
        else:
            base = self
        if user is None and default is None:
            return base
        merged = self._merge(WsiMetadata, base, user, default)
        assert merged is not None
        return merged

    def _remove_confidential(self) -> "WsiDicomizerMetadata":
        return WsiDicomizerMetadata(
            study=None,
            series=None,
            patient=Patient(de_identification=self.patient.de_identification),
            equipment=Equipment(
                manufacturer=self.equipment.manufacturer,
                model_name=self.equipment.model_name,
                software_versions=self.equipment.software_versions,
            ),
            optical_paths=self.optical_paths,
            slide=None,
            label=Label(
                label_in_overview_image=self.label.label_in_overview_image,
                label_in_volume_image=self.label.label_in_volume_image,
                label_is_phi=self.label.label_is_phi,
            ),
            image=Image(
                focus_method=self.image.focus_method,
                extended_depth_of_field=self.image.extended_depth_of_field,
                pixel_spacing=self.image.pixel_spacing,
                focal_plane_spacing=self.image.focal_plane_spacing,
                depth_of_field=self.image.depth_of_field,
            ),
            frame_of_reference_uid=None,
            dimension_organization_uids=None,
        )

    @classmethod
    def _merge(
        cls,
        model_class: Type[ModelType],
        base: Optional[ModelType],
        user: Optional[ModelType],
        default: Optional[ModelType],
    ) -> Optional[ModelType]:
        """Merge three models to a new model.

        - base - model from file.
        - user - user defined model that overrides base.
        - default - user defined model with default values used for fields not defined
        in base or user model.

        """
        not_none = [model for model in [user, base, default] if model is not None]
        if len(not_none) == 0:
            return None
        if len(not_none) == 1:
            return not_none[0]
        assert is_dataclass(model_class)
        attributes = {
            field.name: cls._select_value(field.name, base, user, default)
            for field in fields(model_class)
        }
        return model_class(**attributes)

    @classmethod
    def _select_value(
        cls,
        field_name,
        base: Optional[ModelType],
        user: Optional[ModelType],
        default: Optional[ModelType],
    ) -> Any:
        base_value = getattr(base, field_name, None)
        user_value = getattr(user, field_name, None)
        default_value = getattr(default, field_name, None)
        value = next(
            (
                value
                for value in [user_value, base_value, default_value]
                if value is not None
            ),
            None,
        )
        if is_dataclass(value):
            value = cls._merge(value.__class__, base_value, user_value, default_value)
        return value
