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
from dataclasses import Field, fields, is_dataclass
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
        if user is None:
            user = WsiDicomizerMetadata()
        if default is None:
            default = WsiDicomizerMetadata()
        return WsiDicomizerMetadata(
            study=self._merge(Study, base.study, user.study, default.study),
            series=self._merge(Series, base.series, user.series, default.series),
            patient=self._merge(Patient, base.patient, user.patient, default.patient),
            equipment=self._merge(
                Equipment, base.equipment, user.equipment, default.equipment
            ),
            optical_paths=self._merge_list(
                OpticalPath,
                base.optical_paths,
                user.optical_paths,
                default.optical_paths,
            ),
            slide=self._merge(Slide, base.slide, user.slide, default.slide),
            label=self._merge(Label, base.label, user.label, default.label),
            image=self._merge(Image, base.image, user.image, default.image),
        )

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
    def _merge_list(
        cls,
        model_class: Type[ModelType],
        base: Sequence[ModelType],
        user: Sequence[ModelType],
        default: Sequence[ModelType],
    ) -> Optional[Sequence[ModelType]]:
        models = [model for model in (user, base, default) if len(model) > 0]
        if len(models) == 0:
            # All lists empty
            return []
        if len(models) == 1:
            # Only one list not empty
            return models[0]
        user = cls._repeat_list(base, user)
        default = cls._repeat_list(base, default)
        return [
            cls._merge_not_none(model_class, base_item, user_item, default_item)
            for base_item, user_item, default_item in zip(base, user, default)
        ]

    @staticmethod
    def _repeat_list(
        base: Sequence[ModelType], to_repeat: Sequence[ModelType]
    ) -> Sequence[ModelType]:
        if len(to_repeat) == len(base):
            return to_repeat
        if not len(to_repeat) == 1:
            raise ValueError()
        return [to_repeat[0] for _ in range(len(base))]

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
            field.name: cls._select_value(field, base, user, default)
            for field in fields(model_class)
        }

        return model_class(**attributes)

    @classmethod
    def _merge_not_none(
        cls,
        model_class: Type[ModelType],
        base: Optional[ModelType],
        user: Optional[ModelType],
        default: Optional[ModelType],
    ) -> ModelType:
        merged = cls._merge(model_class, base, user, default)
        assert merged is not None
        return merged

    @classmethod
    def _select_value(
        cls,
        field: Field,
        base: Optional[ModelType],
        user: Optional[ModelType],
        default: Optional[ModelType],
    ) -> Any:
        base_value = getattr(base, field.name, None)
        user_value = getattr(user, field.name, None)
        default_value = getattr(default, field.name, None)
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
