import datetime

from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationStepsCode,
    SpecimenSamplingProcedureCode,
)
from tests.metadata.helpers import assert_dict_equals_code

from wsidicomizer.metadata.sample import (
    Collection,
    Embedding,
    ExtractedSpecimen,
    Fixation,
    Processing,
    Sample,
    SampledSpecimen,
    Sampling,
    SlideSample,
)
from wsidicomizer.metadata.schema.sample import (
    ExtractedSpecimenSchema,
    PreparationStepSchema,
    SampleSchema,
    SerializedSamplingChainConstraint,
    SamplingConstraintSchema,
    SerializedSampling,
    SlideSampleSchema,
    SpecimenSchema,
)
from pydicom.sr.coding import Code
from pydicom.uid import UID


class TestSampleSchema:
    def test_sampling_constraint_serialize(self, extracted_specimen: ExtractedSpecimen):
        # Arrange
        sampling_chain_constraint = extracted_specimen.sample(
            SpecimenSamplingProcedureCode("Dissection")
        )

        # Act
        dumped = SamplingConstraintSchema().dump(sampling_chain_constraint)

        # Arrange
        assert isinstance(dumped, dict)
        assert dumped["identifier"] == sampling_chain_constraint.specimen.identifier
        assert dumped["sampling_step_index"] == 0

    def test_sampling_constraint_deserialize(self):
        # Arrange
        dumped = {"identifier": "specimen", "sampling_step_index": 1}

        # Act
        loaded = SamplingConstraintSchema().load(dumped)

        # Assert
        assert isinstance(loaded, SerializedSamplingChainConstraint)
        assert loaded.identifier == dumped["identifier"]
        assert loaded.sampling_step_index == dumped["sampling_step_index"]

    def test_sampling_serialize(self):
        # Arrange
        specimen = ExtractedSpecimen(
            "specimen",
            AnatomicPathologySpecimenTypesCode("Gross specimen"),
        )
        sampling_1 = specimen.sample(
            SpecimenSamplingProcedureCode("Dissection"),
            datetime.datetime(2023, 8, 5),
            "description",
        )
        sample = SampledSpecimen(
            "sample",
            AnatomicPathologySpecimenTypesCode("Tissue section"),
            [sampling_1],
            [],
        )
        sampling_2 = sample.sample(
            SpecimenSamplingProcedureCode("Block sectioning"),
            datetime.datetime(2023, 8, 5),
            "description",
            [sampling_1],
        )
        assert sampling_2.date_time is not None

        # Act
        dumped = PreparationStepSchema().dump(sampling_2)

        # Assert
        assert isinstance(dumped, dict)
        assert_dict_equals_code(dumped["method"], sampling_2.method)
        assert dumped["date_time"] == sampling_2.date_time.isoformat()
        assert dumped["description"] == sampling_2.description
        assert dumped["preparation_type"] == "sampling"
        assert (
            dumped["sampling_chain_constraints"][0]["identifier"] == specimen.identifier
        )
        assert dumped["sampling_chain_constraints"][0]["sampling_step_index"] == 0

    def test_sampling_deserialize(self):
        # Arrange
        dumped = {
            "method": {
                "value": "434472006",
                "scheme_designator": "SCT",
                "meaning": "Block sectioning",
            },
            "sampling_chain_constraints": [
                {"identifier": "specimen", "sampling_step_index": 0}
            ],
            "date_time": "2023-08-05T00:00:00",
            "description": "description",
            "preparation_type": "sampling",
        }

        # Act
        loaded = PreparationStepSchema().load(dumped)

        # Assert
        assert isinstance(loaded, SerializedSampling)
        assert loaded.sampling_chain_constraints is not None
        assert_dict_equals_code(dumped["method"], loaded.method)
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])
        assert loaded.description == dumped["description"]
        assert (
            loaded.sampling_chain_constraints[0].identifier
            == dumped["sampling_chain_constraints"][0]["identifier"]
        )
        assert (
            loaded.sampling_chain_constraints[0].sampling_step_index
            == dumped["sampling_chain_constraints"][0]["sampling_step_index"]
        )

    def test_collection_serialize(self):
        # Arrange
        collection = Collection(
            SpecimenCollectionProcedureCode("Excision"),
            datetime.datetime(2023, 8, 5),
            "description",
        )
        assert collection.date_time is not None

        # Act
        dumped = PreparationStepSchema().dump(collection)

        # Assert
        assert isinstance(dumped, dict)
        assert_dict_equals_code(dumped["method"], collection.method)
        assert dumped["date_time"] == collection.date_time.isoformat()
        assert dumped["description"] == collection.description
        assert dumped["preparation_type"] == "collection"

    def test_collection_deserialize(self):
        # Arrange
        dumped = {
            "method": {
                "value": "65801008",
                "scheme_designator": "SCT",
                "meaning": "Excision",
            },
            "date_time": "2023-08-05T00:00:00",
            "description": "description",
            "preparation_type": "collection",
        }

        # Act
        loaded = PreparationStepSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Collection)
        assert_dict_equals_code(dumped["method"], loaded.method)
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])
        assert loaded.description == dumped["description"]

    def test_processing_serialize(self):
        # Arrange
        processing = Processing(
            SpecimenPreparationStepsCode("Specimen clearing"),
            datetime.datetime(2023, 8, 5),
        )
        assert processing.date_time is not None

        # Act
        dumped = PreparationStepSchema().dump(processing)

        # Assert
        assert isinstance(dumped, dict)
        assert_dict_equals_code(dumped["method"], processing.method)
        assert dumped["date_time"] == processing.date_time.isoformat()
        assert dumped["preparation_type"] == "processing"

    def test_processing_deserialize(self):
        # Arrange
        dumped = {
            "method": {
                "value": "433452008",
                "scheme_designator": "SCT",
                "meaning": "Specimen clearing",
            },
            "date_time": "2023-08-05T00:00:00",
            "preparation_type": "processing",
        }

        # Act
        loaded = PreparationStepSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Processing)
        assert_dict_equals_code(dumped["method"], loaded.method)
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])

    def test_embedding_serialize(self):
        # Arrange
        embedding = Embedding(
            SpecimenEmbeddingMediaCode("Paraffin wax"),
            datetime.datetime(2023, 8, 5),
        )
        assert embedding.date_time is not None

        # Act
        dumped = PreparationStepSchema().dump(embedding)

        # Assert
        assert isinstance(dumped, dict)
        assert_dict_equals_code(dumped["medium"], embedding.medium)
        assert dumped["date_time"] == embedding.date_time.isoformat()
        assert dumped["preparation_type"] == "embedding"

    def test_embedding_deserialize(self):
        # Arrange
        dumped = {
            "medium": {
                "value": "311731000",
                "scheme_designator": "SCT",
                "meaning": "Paraffin wax",
            },
            "date_time": "2023-08-05T00:00:00",
            "preparation_type": "embedding",
        }

        # Act
        loaded = PreparationStepSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Embedding)
        assert_dict_equals_code(dumped["medium"], loaded.medium)
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])

    def test_fixation_serialize(self):
        # Arrange
        fixation = Fixation(
            SpecimenFixativesCode("Neutral Buffered Formalin"),
            datetime.datetime(2023, 8, 5),
        )
        assert fixation.date_time is not None

        # Act
        dumped = PreparationStepSchema().dump(fixation)

        # Assert
        assert isinstance(dumped, dict)
        assert_dict_equals_code(dumped["fixative"], fixation.fixative)
        assert dumped["date_time"] == fixation.date_time.isoformat()
        assert dumped["preparation_type"] == "fixation"

    def test_fixation_deserialize(self):
        # Arrange
        dumped = {
            "fixative": {
                "value": "434162003",
                "scheme_designator": "SCT",
                "meaning": "Neutral Buffered Formalin",
            },
            "date_time": "2023-08-05T00:00:00",
            "preparation_type": "fixation",
        }

        # Act
        loaded = PreparationStepSchema().load(dumped)

        # Assert
        assert isinstance(loaded, Fixation)
        assert_dict_equals_code(dumped["fixative"], loaded.fixative)
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])

    def test_extracted_specimen_serialize(self, extracted_specimen: ExtractedSpecimen):
        # Arrange
        assert extracted_specimen.extraction_step is not None
        assert extracted_specimen.extraction_step.date_time is not None

        # Act
        dumped = ExtractedSpecimenSchema().dump(extracted_specimen)

        # Assert

        assert isinstance(dumped, dict)
        assert dumped["identifier"] == extracted_specimen.identifier
        assert_dict_equals_code(
            dumped["steps"][0]["method"], extracted_specimen.extraction_step.method
        )
        assert (
            dumped["steps"][0]["date_time"]
            == extracted_specimen.extraction_step.date_time.isoformat()
        )
        assert dumped["steps"][0]["preparation_type"] == "collection"
        assert_dict_equals_code(dumped["type"], extracted_specimen.type)
        assert dumped["specimen_type"] == "extracted"

    def test_extracted_specimen_deserialize(self):
        # Arrange
        dumped = {
            "identifier": "specimen",
            "steps": [
                {
                    "method": {
                        "value": "65801008",
                        "scheme_designator": "SCT",
                        "meaning": "Excision",
                    },
                    "date_time": "2023-08-05T00:00:00",
                    "description": "description",
                    "preparation_type": "collection",
                }
            ],
            "type": {
                "value": "430861001",
                "scheme_designator": "SCT",
                "meaning": "Gross specimen",
            },
            "specimen_type": "extracted",
        }

        # Act
        loaded = ExtractedSpecimenSchema().load(dumped)

        # Assert
        assert isinstance(loaded, dict)
        assert loaded["identifier"] == dumped["identifier"]
        collection = loaded["steps"][0]
        assert isinstance(collection, Collection)
        assert_dict_equals_code(dumped["steps"][0]["method"], collection.method)
        assert collection.date_time == datetime.datetime.fromisoformat(
            dumped["steps"][0]["date_time"]
        )
        assert collection.description == dumped["steps"][0]["description"]
        assert isinstance(loaded["type"], AnatomicPathologySpecimenTypesCode)
        assert_dict_equals_code(dumped["type"], loaded["type"])

    def test_sample_serialize(self, sample: Sample):
        # Arrange
        processing = sample.steps[0]
        assert isinstance(processing, Processing)
        assert processing.date_time is not None

        # Act
        dumped = SampleSchema().dump(sample)

        # Assert
        assert isinstance(dumped, dict)
        assert dumped["identifier"] == sample.identifier
        assert_dict_equals_code(dumped["steps"][0]["method"], processing.method)
        assert dumped["steps"][0]["date_time"] == processing.date_time.isoformat()
        assert dumped["steps"][0]["preparation_type"] == "processing"
        assert_dict_equals_code(dumped["type"], sample.type)
        assert (
            dumped["sampled_from"][0]["identifier"]
            == sample.sampled_from[0].specimen.identifier
        )
        assert dumped["sampled_from"][0]["sampling_step_index"] == 0
        assert dumped["specimen_type"] == "sample"

    def test_sampled_specimen_deserialize(self):
        # Arrange
        dumped = {
            "identifier": "sample",
            "steps": [
                {
                    "method": {
                        "value": "433452008",
                        "scheme_designator": "SCT",
                        "meaning": "Specimen clearing",
                    },
                    "date_time": "2023-08-05T00:00:00",
                    "preparation_type": "processing",
                }
            ],
            "sampled_from": [{"identifier": "specimen", "sampling_step_index": 1}],
            "type": {
                "value": "430856003",
                "scheme_designator": "SCT",
                "meaning": "Tissue section",
            },
            "specimen_type": "sample",
        }

        # Act
        loaded = SampleSchema().load(dumped)

        # Assert
        assert isinstance(loaded, dict)
        assert loaded["identifier"] == dumped["identifier"]
        processing = loaded["steps"][0]
        assert isinstance(processing, Processing)
        assert_dict_equals_code(dumped["steps"][0]["method"], processing.method)
        assert processing.date_time == datetime.datetime.fromisoformat(
            dumped["steps"][0]["date_time"]
        )
        assert isinstance(loaded["type"], AnatomicPathologySpecimenTypesCode)
        assert_dict_equals_code(dumped["type"], loaded["type"])

    def test_slide_sample_serialize(self, slide_sample: SlideSample):
        # Arrange
        assert slide_sample.sampled_from is not None

        # Act
        dumped = SlideSampleSchema().dump(slide_sample)

        # Assert
        assert isinstance(dumped, dict)
        assert dumped["identifier"] == slide_sample.identifier
        assert_dict_equals_code(
            dumped["anatomical_sites"][0], slide_sample.anatomical_sites[0]
        )
        assert (
            dumped["sampled_from"]["identifier"]
            == slide_sample.sampled_from.specimen.identifier
        )
        assert dumped["sampled_from"]["sampling_step_index"] == 0
        assert dumped["uid"] == str(slide_sample.uid)
        assert dumped["position"] == slide_sample.position

        assert dumped["specimen_type"] == "slide"

    def test_slide_sample_deserialize(self):
        # Arrange
        dumped = {
            "identifier": "sample",
            "steps": [],
            "anatomical_sites": [
                {"value": "value", "scheme_designator": "scheme", "meaning": "meaning"}
            ],
            "sampled_from": {"identifier": "sample", "sampling_step_index": 1},
            "uid": "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423",
            "position": "left",
            "specimen_type": "slide",
        }

        # Act
        loaded = SlideSampleSchema().load(dumped)

        # Assert
        assert isinstance(loaded, dict)
        assert loaded["identifier"] == dumped["identifier"]
        anatomical_site = loaded["anatomical_sites"][0]
        assert isinstance(anatomical_site, Code)
        assert_dict_equals_code(dumped["anatomical_sites"][0], anatomical_site)
        assert loaded["uid"] == UID(dumped["uid"])
        assert loaded["position"] == dumped["position"]

    def test_full_slide_sample_serialize(self, slide_sample: SlideSample):
        # Arrange
        assert slide_sample.sampled_from is not None
        sample = slide_sample.sampled_from.specimen
        assert isinstance(sample, Sample)
        specimen = sample.sampled_from[0].specimen

        # Act
        dumped = SpecimenSchema().dump(slide_sample)

        # Assert
        assert isinstance(dumped, list)
        dumpled_slide_sample = dumped[0]
        dumpled_sample = dumped[1]
        dumpled_specimen = dumped[2]

        assert isinstance(dumpled_slide_sample, dict)
        assert dumpled_slide_sample["identifier"] == slide_sample.identifier
        assert (
            dumpled_slide_sample["sampled_from"]["identifier"]
            == slide_sample.sampled_from.specimen.identifier
        )
        assert (
            dumpled_slide_sample["sampled_from"]["sampling_step_index"]
            == slide_sample.sampled_from.index
        )
        assert isinstance(dumpled_sample, dict)
        assert dumpled_sample["identifier"] == sample.identifier
        assert (
            dumpled_sample["sampled_from"][0]["identifier"]
            == sample.sampled_from[0].specimen.identifier
        )
        assert (
            dumpled_sample["sampled_from"][0]["sampling_step_index"]
            == sample.sampled_from[0].index
        )
        assert isinstance(dumpled_specimen, dict)
        assert dumpled_specimen["identifier"] == specimen.identifier

    def test_full_slide_sample_deserialize(self):
        dumped = [
            {
                "identifier": "slide sample",
                "steps": [],
                "anatomical_sites": [
                    {
                        "value": "value",
                        "scheme_designator": "scheme",
                        "meaning": "meaning",
                    }
                ],
                "sampled_from": {"identifier": "sample", "sampling_step_index": 0},
                "uid": "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423",
                "position": "left",
                "specimen_type": "slide",
            },
            {
                "identifier": "sample",
                "steps": [
                    {
                        "method": {
                            "value": "433452008",
                            "scheme_designator": "SCT",
                            "meaning": "Specimen clearing",
                        },
                        "date_time": "2023-08-05T00:00:00",
                        "preparation_type": "processing",
                    },
                    {
                        "method": {
                            "value": "434472006",
                            "scheme_designator": "SCT",
                            "meaning": "Block sectioning",
                        },
                        "sampling_chain_constraints": None,
                        "date_time": "2023-08-05T00:00:00",
                        "description": "Sectioning to slide",
                        "preparation_type": "sampling",
                    },
                ],
                "sampled_from": [{"identifier": "specimen", "sampling_step_index": 0}],
                "type": {
                    "value": "430856003",
                    "scheme_designator": "SCT",
                    "meaning": "Tissue section",
                },
                "specimen_type": "sample",
            },
            {
                "identifier": "specimen",
                "steps": [
                    {
                        "method": {
                            "value": "65801008",
                            "scheme_designator": "SCT",
                            "meaning": "Excision",
                        },
                        "date_time": "2023-08-05T00:00:00",
                        "description": "description",
                        "preparation_type": "collection",
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
                    "value": "430861001",
                    "scheme_designator": "SCT",
                    "meaning": "Gross specimen",
                },
                "specimen_type": "extracted",
            },
        ]

        # Act
        loaded = SpecimenSchema().load(dumped)

        # Assert
        assert isinstance(loaded, list)
        loaded_slide_sample = loaded[0]
        assert isinstance(loaded_slide_sample, SlideSample)
        assert loaded_slide_sample.identifier == dumped[0]["identifier"]
        assert loaded_slide_sample.sampled_from is not None
        sample = loaded_slide_sample.sampled_from.specimen
        assert isinstance(sample, Sample)
        assert sample.identifier == dumped[1]["identifier"]
        specimen = sample.sampled_from[0].specimen
        assert isinstance(specimen, ExtractedSpecimen)
        assert specimen.identifier == dumped[2]["identifier"]

    def test_slide_sample_rountrip(self, slide_sample: SlideSample):
        # Arrange

        # Act
        dumped = SpecimenSchema().dump(slide_sample)
        loaded = SpecimenSchema().load(dumped)

        # Assert
        assert str(loaded[0]) == str(slide_sample)
