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

"""Metadata for isyntax file."""

from wsidicom.metadata.optical_path import OpticalPath

from isyntax import ISyntax
from wsidicomizer.metadata import WsiDicomizerMetadata


class ISyntaxMetadata(WsiDicomizerMetadata):
    def __init__(self, slide: ISyntax):
        icc_profile = slide.read_icc_profile()
        if icc_profile is not None:
            optical_path = OpticalPath(icc_profile=icc_profile)
            optical_paths = [optical_path]
        else:
            optical_paths = None
        super().__init__(optical_paths=optical_paths)
