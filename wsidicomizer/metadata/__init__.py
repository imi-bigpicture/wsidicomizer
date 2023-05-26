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

""""""

from wsidicomizer.metadata.wsi import WsiMetadata
from wsidicomizer.metadata.equipment import Equipment
from wsidicomizer.metadata.image import Image, ImageCoordinateSystem
from wsidicomizer.metadata.label import Label
from wsidicomizer.metadata.optical_path import OpticalPath
from wsidicomizer.metadata.patient import Patient, PatientDeIdentification
from wsidicomizer.metadata.sample import Block, Specimen, SimpleSample
from wsidicomizer.metadata.series import Series
from wsidicomizer.metadata.slide import Slide, SampleLocation
from wsidicomizer.metadata.study import Study
