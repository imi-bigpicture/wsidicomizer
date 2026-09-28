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

"""Importing wsidicomizer must leave pydicom's global configuration alone."""

import importlib

import pytest
from pydicom import config


@pytest.mark.unittest
class TestPydicomConfig:
    def test_import_does_not_change_pydicom_config(self):
        # Arrange

        # Act
        importlib.import_module("wsidicomizer")

        # Assert
        assert not config._use_future
        assert config.settings.reading_validation_mode == config.WARN
        assert config.settings.writing_validation_mode == config.WARN
