import datetime
from wsidicomizer.metadata import ExtractedSpecimen
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    SpecimenCollectionProcedureCode,
    SpecimenFixativesCode,
    SpecimenSamplingProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenStainsCode,
)

from wsidicomizer.metadata.sample import (
    Collection,
    Embedding,
    Fixation,
    Sample,
    SlideSample,
    SlideSamplePosition,
)
from pydicom.sr.coding import Code
from pydicom.uid import UID
from wsidicomizer.metadata.schema.slide import SlideSchema

from wsidicomizer.metadata.slide import Slide


class TestSlideSchema:
    def test_slide_serialize(self):
        # Arrange
        part_1 = ExtractedSpecimen(
            "part 1",
            AnatomicPathologySpecimenTypesCode("tissue specimen"),
            Collection(
                SpecimenCollectionProcedureCode("Specimen collection"),
                datetime.datetime(2023, 8, 5),
                "Extracted",
            ),
            [
                Fixation(
                    SpecimenFixativesCode("Neutral Buffered Formalin"),
                    datetime.datetime(2023, 8, 5),
                )
            ],
        )

        part_2 = ExtractedSpecimen(
            "part 2",
            AnatomicPathologySpecimenTypesCode("tissue specimen"),
            Collection(
                SpecimenCollectionProcedureCode("Specimen collection"),
                datetime.datetime(2023, 8, 5),
                "Extracted",
            ),
            [
                Fixation(
                    SpecimenFixativesCode("Neutral Buffered Formalin"),
                    datetime.datetime(2023, 8, 5),
                )
            ],
        )

        block = Sample(
            "block 1",
            AnatomicPathologySpecimenTypesCode("tissue specimen"),
            [
                part_1.sample(
                    SpecimenSamplingProcedureCode("Dissection"),
                    datetime.datetime(2023, 8, 5),
                    "Sampling to block",
                ),
                part_1.sample(
                    SpecimenSamplingProcedureCode("Dissection"),
                    datetime.datetime(2023, 8, 5),
                    "Sampling to block",
                ),
            ],
            [
                Embedding(
                    SpecimenEmbeddingMediaCode("Paraffin wax"),
                    datetime.datetime(2023, 8, 5),
                )
            ],
        )

        sample_1 = SlideSample(
            "Sample 1",
            [Code("value", "schema", "meaning")],
            block.sample(
                SpecimenSamplingProcedureCode("Block sectioning"),
                datetime.datetime(2023, 8, 5),
                "Sampling to slide",
                [part_1.samplings[0]],
            ),
            UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"),
            SlideSamplePosition(0, 0, 0),
        )

        sample_2 = SlideSample(
            "Sample 2",
            [Code("value", "schema", "meaning")],
            block.sample(
                SpecimenSamplingProcedureCode("Block sectioning"),
                datetime.datetime(2023, 8, 5),
                "Sampling to slide",
                [part_1.samplings[1]],
            ),
            UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445424"),
            position=SlideSamplePosition(10, 0, 0),
        )

        stains = [
            SpecimenStainsCode("hematoxylin stain"),
            SpecimenStainsCode("water soluble eosin stain"),
        ]

        slide = Slide(identifier="Slide 1", stains=stains, samples=[sample_1, sample_2])

        # Act
        dumped = SlideSchema().dump(slide)

        # Assert
        print(dumped)
        # assert False
        assert isinstance(dumped, dict)
        assert dumped["identifier"] == slide.identifier

    def test_slide_deserialize(self):
        # Arrange
        dumped = {
            "identifier": "Slide 1",
            "stains": [
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
            "samples": [
                [
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
                                "specimen": "block 1",
                                "method": {
                                    "value": "434472006",
                                    "scheme_designator": "SCT",
                                    "meaning": "Block sectioning",
                                },
                                "sampling_chain_constraints": [
                                    {"identifier": "part 1", "sampling_step_index": 2}
                                ],
                                "date_time": "2023-08-05T00:00:00",
                                "description": "Sampling to slide",
                                "preparation_type": "sampling",
                            },
                            {
                                "specimen": "block 1",
                                "method": {
                                    "value": "434472006",
                                    "scheme_designator": "SCT",
                                    "meaning": "Block sectioning",
                                },
                                "sampling_chain_constraints": [
                                    {"identifier": "part 1", "sampling_step_index": 2}
                                ],
                                "date_time": "2023-08-05T00:00:00",
                                "description": "Sampling to slide",
                                "preparation_type": "sampling",
                            },
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
                                "specimen": "part 1",
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
                            {
                                "specimen": "part 1",
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
                ],
                [
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
                        "uid": "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445424",
                        "position": {"x": 10, "y": 0, "z": 0},
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
                                "specimen": "block 1",
                                "method": {
                                    "value": "434472006",
                                    "scheme_designator": "SCT",
                                    "meaning": "Block sectioning",
                                },
                                "sampling_chain_constraints": [
                                    {"identifier": "part 1", "sampling_step_index": 2}
                                ],
                                "date_time": "2023-08-05T00:00:00",
                                "description": "Sampling to slide",
                                "preparation_type": "sampling",
                            },
                            {
                                "specimen": "block 1",
                                "method": {
                                    "value": "434472006",
                                    "scheme_designator": "SCT",
                                    "meaning": "Block sectioning",
                                },
                                "sampling_chain_constraints": [
                                    {"identifier": "part 1", "sampling_step_index": 2}
                                ],
                                "date_time": "2023-08-05T00:00:00",
                                "description": "Sampling to slide",
                                "preparation_type": "sampling",
                            },
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
                                "specimen": "part 1",
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
                            {
                                "specimen": "part 1",
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
                ],
            ],
        }

        # Act
        loaded = SlideSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Slide)
