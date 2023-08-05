import datetime

from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationStepsCode,
    SpecimenSamplingProcedureCode,
)

from wsidicomizer.metadata.sample import (
    Collection,
    Embedding,
    ExtractedSpecimen,
    Fixation,
    Processing,
    Sample,
    SampledSpecimen,
    SlideSample,
)
from wsidicomizer.metadata.schema.sample import (
    ExtractedSpecimenSchema,
    PreparationStepSchema,
    SampleSchema,
    SamplingChainConstraintSimplified,
    SamplingConstraintSchema,
    SamplingSimplified,
    SlideSampleSchema,
    SpecimenSchema,
)
from pydicom.sr.coding import Code
from pydicom.uid import UID


class TestSampleSchema:
    def test_sampling_constraint_serialize(self):
        # Arrange
        sampling_chain_constraint = SamplingChainConstraintSimplified("specimen", 1)

        # Act
        dumped = SamplingConstraintSchema().dump(sampling_chain_constraint)

        # Arrange
        assert isinstance(dumped, dict)
        assert dumped["identifier"] == sampling_chain_constraint.identifier
        assert (
            dumped["sampling_step_index"]
            == sampling_chain_constraint.sampling_step_index
        )

    def test_sampling_constraint_deserialize(self):
        # Arrange
        dumped = {"identifier": "specimen", "sampling_step_index": 1}

        # Act
        loaded = SamplingConstraintSchema().load(dumped)

        # Assert
        assert isinstance(loaded, SamplingChainConstraintSimplified)
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

        # Act
        dumped = PreparationStepSchema().dump(sampling_2)

        # Assert
        assert isinstance(dumped, dict)
        assert sampling_2.date_time is not None
        assert dumped["specimen"] == sampling_2.specimen.identifier
        assert dumped["method"]["value"] == sampling_2.method.value
        assert (
            dumped["method"]["scheme_designator"] == sampling_2.method.scheme_designator
        )
        assert dumped["method"]["meaning"] == sampling_2.method.meaning
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
            "specimen": "sample",
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
        assert isinstance(loaded, SamplingSimplified)
        assert loaded.sampling_chain_constraints is not None
        assert loaded.specimen == dumped["specimen"]
        assert loaded.method.value == dumped["method"]["value"]
        assert loaded.method.scheme_designator == dumped["method"]["scheme_designator"]
        assert loaded.method.meaning == dumped["method"]["meaning"]
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

        # Act
        dumped = PreparationStepSchema().dump(collection)

        # Assert
        assert isinstance(dumped, dict)
        assert collection.date_time is not None
        assert dumped["method"]["value"] == collection.method.value
        assert (
            dumped["method"]["scheme_designator"] == collection.method.scheme_designator
        )
        assert dumped["method"]["meaning"] == collection.method.meaning
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
        assert loaded.method.value == dumped["method"]["value"]
        assert loaded.method.scheme_designator == dumped["method"]["scheme_designator"]
        assert loaded.method.meaning == dumped["method"]["meaning"]
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])
        assert loaded.description == dumped["description"]

    def test_processing_serialize(self):
        # Arrange
        processing = Processing(
            SpecimenPreparationStepsCode("Specimen clearing"),
            datetime.datetime(2023, 8, 5),
        )

        # Act
        dumped = PreparationStepSchema().dump(processing)

        # Assert
        assert isinstance(dumped, dict)
        assert processing.date_time is not None
        assert dumped["method"]["value"] == processing.method.value
        assert (
            dumped["method"]["scheme_designator"] == processing.method.scheme_designator
        )
        assert dumped["method"]["meaning"] == processing.method.meaning
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
        assert loaded.method.value == dumped["method"]["value"]
        assert loaded.method.scheme_designator == dumped["method"]["scheme_designator"]
        assert loaded.method.meaning == dumped["method"]["meaning"]
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])

    def test_embedding_serialize(self):
        # Arrange
        embedding = Embedding(
            SpecimenEmbeddingMediaCode("Paraffin wax"),
            datetime.datetime(2023, 8, 5),
        )

        # Act
        dumped = PreparationStepSchema().dump(embedding)

        # Assert
        assert isinstance(dumped, dict)
        assert embedding.date_time is not None
        assert dumped["medium"]["value"] == embedding.medium.value
        assert (
            dumped["medium"]["scheme_designator"] == embedding.medium.scheme_designator
        )
        assert dumped["medium"]["meaning"] == embedding.medium.meaning
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
        assert loaded.medium.value == dumped["medium"]["value"]
        assert loaded.medium.scheme_designator == dumped["medium"]["scheme_designator"]
        assert loaded.medium.meaning == dumped["medium"]["meaning"]
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])

    def test_fixation_serialize(self):
        # Arrange
        fixation = Fixation(
            SpecimenFixativesCode("Neutral Buffered Formalin"),
            datetime.datetime(2023, 8, 5),
        )

        # Act
        dumped = PreparationStepSchema().dump(fixation)

        # Assert
        assert isinstance(dumped, dict)
        assert fixation.date_time is not None
        assert dumped["fixative"]["value"] == fixation.fixative.value
        assert (
            dumped["fixative"]["scheme_designator"]
            == fixation.fixative.scheme_designator
        )
        assert dumped["fixative"]["meaning"] == fixation.fixative.meaning
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
        assert loaded.fixative.value == dumped["fixative"]["value"]
        assert (
            loaded.fixative.scheme_designator == dumped["fixative"]["scheme_designator"]
        )
        assert loaded.fixative.meaning == dumped["fixative"]["meaning"]
        assert loaded.date_time == datetime.datetime.fromisoformat(dumped["date_time"])

    def test_extracted_specimen_serialize(self):
        # Arrange
        collection = Collection(
            SpecimenCollectionProcedureCode("Excision"),
            datetime.datetime(2023, 8, 5),
            "description",
        )
        specimen = ExtractedSpecimen(
            "specimen", AnatomicPathologySpecimenTypesCode("Gross specimen"), collection
        )

        # Act
        dumped = ExtractedSpecimenSchema().dump(specimen)

        # Assert
        assert isinstance(dumped, dict)
        assert collection.date_time is not None
        assert dumped["identifier"] == specimen.identifier
        assert dumped["steps"][0]["method"]["value"] == collection.method.value
        assert (
            dumped["steps"][0]["method"]["scheme_designator"]
            == collection.method.scheme_designator
        )
        assert dumped["steps"][0]["method"]["meaning"] == collection.method.meaning

        assert dumped["steps"][0]["date_time"] == collection.date_time.isoformat()
        assert dumped["steps"][0]["preparation_type"] == "collection"
        assert dumped["type"]["value"] == specimen.type.value
        assert dumped["type"]["scheme_designator"] == specimen.type.scheme_designator
        assert dumped["type"]["meaning"] == specimen.type.meaning
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
        assert collection.method.value == dumped["steps"][0]["method"]["value"]
        assert (
            collection.method.scheme_designator
            == dumped["steps"][0]["method"]["scheme_designator"]
        )
        assert collection.method.meaning == dumped["steps"][0]["method"]["meaning"]
        assert collection.date_time == datetime.datetime.fromisoformat(
            dumped["steps"][0]["date_time"]
        )
        assert collection.description == dumped["steps"][0]["description"]
        type = loaded["type"]
        assert isinstance(type, AnatomicPathologySpecimenTypesCode)
        assert type.value == dumped["type"]["value"]
        assert type.meaning == dumped["type"]["meaning"]
        assert type.scheme_designator == dumped["type"]["scheme_designator"]

    def test_sampled_specimen_serialize(self):
        # Arrange
        processing = Processing(
            SpecimenPreparationStepsCode("Specimen clearing"),
            datetime.datetime(2023, 8, 5),
        )
        sample = Sample(
            "sample",
            AnatomicPathologySpecimenTypesCode("Tissue section"),
            [],
            [processing],
        )

        # Act
        dumped = SampleSchema().dump(sample)

        # Assert
        assert isinstance(dumped, dict)
        assert processing.date_time is not None
        assert dumped["identifier"] == sample.identifier
        assert dumped["steps"][0]["method"]["value"] == processing.method.value
        assert (
            dumped["steps"][0]["method"]["scheme_designator"]
            == processing.method.scheme_designator
        )
        assert dumped["steps"][0]["method"]["meaning"] == processing.method.meaning
        assert dumped["steps"][0]["date_time"] == processing.date_time.isoformat()
        assert dumped["steps"][0]["preparation_type"] == "processing"
        assert dumped["type"]["value"] == sample.type.value
        assert dumped["type"]["scheme_designator"] == sample.type.scheme_designator
        assert dumped["type"]["meaning"] == sample.type.meaning
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
        assert processing.method.value == dumped["steps"][0]["method"]["value"]
        assert (
            processing.method.scheme_designator
            == dumped["steps"][0]["method"]["scheme_designator"]
        )
        assert processing.method.meaning == dumped["steps"][0]["method"]["meaning"]
        assert processing.date_time == datetime.datetime.fromisoformat(
            dumped["steps"][0]["date_time"]
        )
        type = loaded["type"]
        assert isinstance(type, AnatomicPathologySpecimenTypesCode)
        assert type.value == dumped["type"]["value"]
        assert type.meaning == dumped["type"]["meaning"]
        assert type.scheme_designator == dumped["type"]["scheme_designator"]

    def test_slide_sample_serialize(self):
        # Arrange
        slide_sample = SlideSample(
            "sample",
            [Code("value", "scheme", "meaning")],
            uid=UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445423"),
            position="left",
        )

        # Act
        dumped = SlideSampleSchema().dump(slide_sample)

        # Assert
        assert isinstance(dumped, dict)
        assert dumped["identifier"] == slide_sample.identifier
        assert (
            dumped["anatomical_sites"][0]["value"]
            == slide_sample.anatomical_sites[0].value
        )
        assert (
            dumped["anatomical_sites"][0]["scheme_designator"]
            == slide_sample.anatomical_sites[0].scheme_designator
        )
        assert (
            dumped["anatomical_sites"][0]["meaning"]
            == slide_sample.anatomical_sites[0].meaning
        )
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
        assert anatomical_site.value == dumped["anatomical_sites"][0]["value"]
        assert (
            anatomical_site.scheme_designator
            == dumped["anatomical_sites"][0]["scheme_designator"]
        )
        assert anatomical_site.meaning == dumped["anatomical_sites"][0]["meaning"]
        assert loaded["uid"] == UID(dumped["uid"])
        assert loaded["position"] == dumped["position"]
