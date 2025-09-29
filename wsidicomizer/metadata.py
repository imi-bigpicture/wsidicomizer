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
from dataclasses import Field, fields, is_dataclass, replace
from typing import Any, Callable, Optional, Sequence, Type, TypeVar

from pydicom import Dataset
from pydicom.uid import UID
from wsidicom.metadata import (
    Equipment,
    Image,
    Label,
    OpticalPath,
    Overview,
    Patient,
    Pyramid,
    Series,
    Slide,
    Study,
    WsiMetadata,
)

ModelType = TypeVar("ModelType")
ModuleWithImage = TypeVar("ModuleWithImage", Pyramid, Label, Overview)


class WsiDicomizerMetadata(WsiMetadata):
    """Subclass of WsiMetadata that can be constructed with optional parameters."""

    def __init__(
        self,
        study: Optional[Study] = None,
        series: Optional[Series] = None,
        patient: Optional[Patient] = None,
        equipment: Optional[Equipment] = None,
        pyramid: Optional[Pyramid] = None,
        slide: Optional[Slide] = None,
        label: Optional[Label] = None,
        overview: Optional[Overview] = None,
        frame_of_reference_uid: Optional[UID] = None,
        dimension_organization_uids: Optional[Sequence[UID]] = None,
    ):
        super().__init__(
            study if study is not None else Study(),
            series if series is not None else Series(),
            patient if patient is not None else Patient(),
            equipment if equipment is not None else Equipment(),
            slide if slide is not None else Slide(),
            pyramid if pyramid is not None else Pyramid(Image(), []),
            label if label is not None else Label(),
            overview,
            frame_of_reference_uid,
            dimension_organization_uids,
        )

    def merge(
        self,
        user: Optional[WsiMetadata],
        default: Optional[WsiMetadata],
        include_confidential: bool,
    ) -> "WsiDicomizerMetadata":
        if not include_confidential:
            base = self._remove_confidential()
        else:
            base = self
        if user is None and default is None:
            return self._merge_not_none(WsiDicomizerMetadata, base, None, None)
        if user is None:
            user = WsiDicomizerMetadata()
        if default is None:
            default = WsiDicomizerMetadata()

        frame_of_reference_uid = base.frame_of_reference_uid
        if user.frame_of_reference_uid is not None:
            frame_of_reference_uid = user.frame_of_reference_uid
        if frame_of_reference_uid is None:
            frame_of_reference_uid = default.frame_of_reference_uid
        dimension_organization_uids = base.dimension_organization_uids
        if user.dimension_organization_uids is not None:
            dimension_organization_uids = user.dimension_organization_uids
        if dimension_organization_uids is None:
            dimension_organization_uids = default.dimension_organization_uids
        # label = self._merge_module_with_image(
        #     Label, base.label, user.label, default.label
        # )
        #     overview = self._merge_module_with_image(
        #         Overview, base.overview, user.overview, default.overview
        #     )
        # if ensure_label:
        #     if label is None:
        #         label = Label(image=Image(), optical_paths=[])
        #     elif label.image is None:
        #         label = replace(label, image=Image())
        #     elif label.optical_paths is None:
        #         label = replace(label, optical_paths=[])
        # if ensure_overview:
        #     if overview is None:
        #         overview = Overview(image=Image(), optical_paths=[])
        #     if overview.image is None:
        #         overview = replace(overview, image=Image())
        #     elif overview.optical_paths is None:
        #         overview = replace(overview, optical_paths=[])
        return WsiDicomizerMetadata(
            study=self._merge(Study, base.study, user.study, default.study),
            series=self._merge(Series, base.series, user.series, default.series),
            patient=self._merge(Patient, base.patient, user.patient, default.patient),
            equipment=self._merge(
                Equipment, base.equipment, user.equipment, default.equipment
            ),
            slide=self._merge(Slide, base.slide, user.slide, default.slide),
            pyramid=self._merge_module_with_image(
                Pyramid, base.pyramid, user.pyramid, default.pyramid
            ),
            label=self._merge_module_with_image(
                Label, base.label, user.label, default.label
            ),
            overview=self._merge_module_with_image(
                Overview, base.overview, user.overview, default.overview
            ),
            frame_of_reference_uid=frame_of_reference_uid,
            dimension_organization_uids=dimension_organization_uids,
        )

    def _remove_confidential(self) -> "WsiDicomizerMetadata":
        return WsiDicomizerMetadata(
            study=None,
            series=None,
            patient=self.patient.remove_confidential() if self.patient else None,
            equipment=self.equipment.remove_confidential() if self.equipment else None,
            slide=None,
            pyramid=self.pyramid.remove_confidential() if self.pyramid else None,
            label=self.label.remove_confidential() if self.label else None,
            overview=self.overview.remove_confidential() if self.overview else None,
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
    ) -> Sequence[ModelType]:
        models = [model for model in (user, base, default) if len(model) > 0]
        if len(models) == 0 or all(item is None for model in models for item in model):
            # All lists empty
            return []
        if len(models) == 1:
            # Only one list not empty
            return models[0]
        user_expanded = cls._repeat_list(base, user)
        default_expanded = cls._repeat_list(base, default)
        return [
            cls._merge_not_none(model_class, base_item, user_item, default_item)
            for base_item, user_item, default_item in zip(
                base, user_expanded, default_expanded
            )
        ]

    @staticmethod
    def _repeat_list(
        base: Sequence[ModelType], to_repeat: Sequence[ModelType]
    ) -> Sequence[Optional[ModelType]]:
        if len(to_repeat) > 1 and len(to_repeat) != len(base):
            raise ValueError(
                "List to repeat must have length 0, 1 or length of base. "
                f"Length of list to repeat: {len(to_repeat)}. "
                f"Length of base: {len(base)}."
            )
        if len(to_repeat) == len(base):
            return to_repeat
        if len(to_repeat) == 0:
            item_to_repeat = None
        else:
            item_to_repeat = to_repeat[0]
        return [item_to_repeat for _ in range(len(base))]

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
        if is_dataclass(value) and isinstance(value, object):
            value = cls._merge(type(value), base_value, user_value, default_value)
        return value

    @classmethod
    def _merge_module_with_image(
        cls,
        model_class: Type[ModuleWithImage],
        base: Optional[ModuleWithImage],
        user: Optional[ModuleWithImage],
        default: Optional[ModuleWithImage],
    ) -> Optional[ModuleWithImage]:
        not_none = [model for model in [user, base, default] if model is not None]
        if len(not_none) == 0:
            return None
        assert is_dataclass(model_class)
        attributes = {
            field.name: cls._select_value(field, base, user, default)
            for field in fields(model_class)
            if field.name != "optical_paths"
        }
        attributes["optical_paths"] = cls._merge_list(
            OpticalPath,
            (
                base.optical_paths
                if base is not None and base.optical_paths is not None
                else []
            ),
            (
                user.optical_paths
                if user is not None and user.optical_paths is not None
                else []
            ),
            (
                default.optical_paths
                if default is not None and default.optical_paths is not None
                else []
            ),
        )

        return model_class(**attributes)


MetadataPostProcessor = Callable[[Dataset, WsiMetadata], Dataset]
