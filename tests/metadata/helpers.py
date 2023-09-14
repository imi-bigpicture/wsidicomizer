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

from typing import Dict, Union

from pydicom.sr.coding import Code
from wsidicom.conceptcode import ConceptCode


def bool_to_dicom_literal(value: bool) -> str:
    if value:
        return "YES"
    return "NO"


def assert_dict_equals_code(
    dumped_code: Dict[str, str], expected_code: Union[Code, ConceptCode]
):
    assert dumped_code["value"] == expected_code.value
    assert dumped_code["scheme_designator"] == expected_code.scheme_designator
    assert dumped_code["meaning"] == expected_code.meaning
    assert dumped_code.get("scheme_version", None) == expected_code.scheme_version
