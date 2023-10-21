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
from abc import ABCMeta
from dataclasses import dataclass, fields, is_dataclass
from typing import (
    Any,
    Dict,
    Optional,
    Type,
    TypeVar,
)

ModelType = TypeVar("ModelType")


@dataclass
class ModelMerger(metaclass=ABCMeta):
    """Base model."""

    @classmethod
    def merge(
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
        attributes: Dict[str, Any] = {}
        for field in fields(model_class):
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
                value = cls.merge(
                    value.__class__, base_value, user_value, default_value
                )

            attributes[field.name] = value
        return model_class(**attributes)
