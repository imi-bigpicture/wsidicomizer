import pytest


@pytest.fixture()
def json_slide():
    yield {
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
