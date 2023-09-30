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

from typing import Any, Dict
from tests.metadata.helpers import assert_dict_equals_code
from wsidicomizer.metadata.sample import SlideSamplePosition
from wsidicomizer.metadata.json_schema.slide import SlideJsonSchema
from wsidicomizer.metadata.slide import Slide
from wsidicom.conceptcode import SpecimenStainsCode


class TestSlideJsonSchema:
    def test_slide_serialize(self, slide: Slide):
        # Arrange

        # Act
        dumped = SlideJsonSchema().dump(slide)

        # Assert
        assert slide.stainings is not None
        assert slide.samples is not None
        assert isinstance(dumped, dict)
        assert dumped["identifier"] == slide.identifier
        for index, staining in enumerate(slide.stainings):
            dumped_staining = dumped["stainings"][index]
            for stain_index, stain in enumerate(staining.substances):
                assert isinstance(stain, SpecimenStainsCode)
                assert_dict_equals_code(
                    dumped_staining["substances"][stain_index], stain
                )

        sample = slide.samples[0]
        assert isinstance(sample.position, SlideSamplePosition)
        dumped_sample = dumped["samples"][0]
        assert dumped_sample["identifier"] == sample.identifier
        assert_dict_equals_code(
            dumped_sample["anatomical_sites"][0], sample.anatomical_sites[0]
        )
        assert dumped_sample["uid"] == str(sample.uid)
        assert dumped_sample["position"]["x"] == sample.position.x
        assert dumped_sample["position"]["y"] == sample.position.y
        assert dumped_sample["position"]["z"] == sample.position.z

        assert sample.sampled_from is not None
        block_1 = sample.sampled_from.specimen
        dumped_block_1 = dumped["samples"][1]
        assert dumped_block_1["identifier"] == block_1.identifier
        assert_dict_equals_code(dumped_block_1["type"], block_1.type)

    def test_slide_deserialize(self, json_slide: Dict[str, Any]):
        # Arrange

        # Act
        loaded = SlideJsonSchema().load(json_slide)

        # Assert
        assert isinstance(loaded, Slide)
