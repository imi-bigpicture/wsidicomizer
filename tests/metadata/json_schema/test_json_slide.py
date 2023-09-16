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

from tests.metadata.helpers import assert_dict_equals_code
from wsidicomizer.metadata.sample import SlideSamplePosition
from wsidicomizer.metadata.json_schema.slide import SlideSchema
from wsidicomizer.metadata.slide import Slide
from wsidicom.conceptcode import SpecimenStainsCode


class TestSlideSchema:
    def test_slide_serialize(self, slide: Slide):
        # Arrange

        # Act
        dumped = SlideSchema().dump(slide)

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
        assert dumped_sample["specimen_type"] == "slide"

        assert sample.sampled_from is not None
        block_1 = sample.sampled_from.specimen
        dumped_block_1 = dumped["samples"][1]
        assert dumped_block_1["identifier"] == block_1.identifier
        assert_dict_equals_code(dumped_block_1["type"], block_1.type)
        assert dumped_block_1["specimen_type"] == "sample"

    def test_slide_deserialize(self):
        # Arrange
        dumped = {
            "identifier": "Slide 1",
            "stainings": [
                {
                    "substances": [
                        {
                            "value": "12710003",
                            "scheme_designator": "SCT",
                            "meaning": "hematoxylin stain",
                        },
                        {
                            "value": "36879007",
                            "scheme_designator": "SCT",
                            "meaning": "water soluble eosin stain",
                        },
                    ],
                    "date_time": "2023-08-05T00:00:00",
                }
            ],
            "samples": [
                {
                    "identifier": "Sample 1",
                    "steps": [],
                    "anatomical_sites": [
                        {
                            "value": "value",
                            "scheme_designator": "schema",
                            "meaning": "meaning",
                        }
                    ],
                    "sampled_from": {"identifier": "block 1", "sampling_step_index": 0},
                    "uid": "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423",
                    "position": {"x": 0, "y": 0, "z": 0},
                    "specimen_type": "slide",
                },
                {
                    "identifier": "block 1",
                    "steps": [
                        {
                            "medium": {
                                "value": "311731000",
                                "scheme_designator": "SCT",
                                "meaning": "Paraffin wax",
                            },
                            "date_time": "2023-08-05T00:00:00",
                            "preparation_type": "embedding",
                        },
                        {
                            "method": {
                                "value": "434472006",
                                "scheme_designator": "SCT",
                                "meaning": "Block sectioning",
                            },
                            "sampling_chain_constraints": [
                                {"identifier": "part 1", "sampling_step_index": 0}
                            ],
                            "date_time": "2023-08-05T00:00:00",
                            "description": "Sampling to slide",
                            "preparation_type": "sampling",
                        },
                        {
                            "method": {
                                "value": "434472006",
                                "scheme_designator": "SCT",
                                "meaning": "Block sectioning",
                            },
                            "sampling_chain_constraints": [
                                {"identifier": "part 2", "sampling_step_index": 0}
                            ],
                            "date_time": "2023-08-05T00:00:00",
                            "description": "Sampling to slide",
                            "preparation_type": "sampling",
                        },
                    ],
                    "sampled_from": [
                        {"identifier": "part 1", "sampling_step_index": 0},
                        {"identifier": "part 2", "sampling_step_index": 0},
                    ],
                    "type": {
                        "value": "119376003",
                        "scheme_designator": "SCT",
                        "meaning": "tissue specimen",
                    },
                    "specimen_type": "sample",
                },
                {
                    "identifier": "part 1",
                    "steps": [
                        {
                            "method": {
                                "value": "17636008",
                                "scheme_designator": "SCT",
                                "meaning": "Specimen collection",
                            },
                            "date_time": "2023-08-05T00:00:00",
                            "description": "Extracted",
                            "preparation_type": "collection",
                        },
                        {
                            "fixative": {
                                "value": "434162003",
                                "scheme_designator": "SCT",
                                "meaning": "Neutral Buffered Formalin",
                            },
                            "date_time": "2023-08-05T00:00:00",
                            "preparation_type": "fixation",
                        },
                        {
                            "method": {
                                "value": "122459003",
                                "scheme_designator": "SCT",
                                "meaning": "Dissection",
                            },
                            "sampling_chain_constraints": None,
                            "date_time": "2023-08-05T00:00:00",
                            "description": "Sampling to block",
                            "preparation_type": "sampling",
                        },
                    ],
                    "type": {
                        "value": "119376003",
                        "scheme_designator": "SCT",
                        "meaning": "tissue specimen",
                    },
                    "specimen_type": "extracted",
                },
                {
                    "identifier": "part 2",
                    "steps": [
                        {
                            "method": {
                                "value": "17636008",
                                "scheme_designator": "SCT",
                                "meaning": "Specimen collection",
                            },
                            "date_time": "2023-08-05T00:00:00",
                            "description": "Extracted",
                            "preparation_type": "collection",
                        },
                        {
                            "fixative": {
                                "value": "434162003",
                                "scheme_designator": "SCT",
                                "meaning": "Neutral Buffered Formalin",
                            },
                            "date_time": "2023-08-05T00:00:00",
                            "preparation_type": "fixation",
                        },
                        {
                            "method": {
                                "value": "122459003",
                                "scheme_designator": "SCT",
                                "meaning": "Dissection",
                            },
                            "sampling_chain_constraints": None,
                            "date_time": "2023-08-05T00:00:00",
                            "description": "Sampling to block",
                            "preparation_type": "sampling",
                        },
                    ],
                    "type": {
                        "value": "119376003",
                        "scheme_designator": "SCT",
                        "meaning": "tissue specimen",
                    },
                    "specimen_type": "extracted",
                },
                {
                    "identifier": "Sample 2",
                    "steps": [],
                    "anatomical_sites": [
                        {
                            "value": "value",
                            "scheme_designator": "schema",
                            "meaning": "meaning",
                        }
                    ],
                    "sampled_from": {"identifier": "block 1", "sampling_step_index": 1},
                    "uid": "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445424",
                    "position": {"x": 10, "y": 0, "z": 0},
                    "specimen_type": "slide",
                },
            ],
        }

        # Act
        loaded = SlideSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Slide)
