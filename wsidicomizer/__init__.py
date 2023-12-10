#    Copyright 2021, 2022, 2023 SECTRA AB
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

from wsidicomizer.dataset import (
    create_brightfield_optical_path_module,
    create_device_module,
    create_patient_module,
    create_sample,
    create_specimen_module,
    create_study_module,
)
from wsidicomizer.wsidicomizer import WsiDicomizer

__version__ = "0.11.0"
