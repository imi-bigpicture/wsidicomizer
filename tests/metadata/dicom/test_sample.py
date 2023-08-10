from typing import Dict, Union
from pydicom import Dataset
from wsidicomizer.metadata.sample import (
    Collection,
    Embedding,
    ExtractedSpecimen,
    Fixation,
    Processing,
    Sampling,
    Specimen,
    SpecimenIdentifier,
)
from highdicom.content import (
    SpecimenPreparationStep,
    SpecimenCollection,
    IssuerOfIdentifier,
    SpecimenProcessing,
    SpecimenSampling,
)
from wsidicom.conceptcode import (
    SpecimenCollectionProcedureCode,
    SpecimenPreparationStepsCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenSamplingProcedureCode,
)


class TestSample:
    def test_collection_from_dataset(self):
        # Arrange
        method = SpecimenCollectionProcedureCode("Excision")
        dataset = SpecimenPreparationStep(
            "identifier",
            SpecimenCollection(
                procedure=method.code,
            ),
            issuer_of_specimen_id=IssuerOfIdentifier("issuer"),
            processing_description="description",
        )

        # Act
        collection = Collection.from_dataset(dataset)

        # Assert
        assert collection.method == method

    def test_sampling_from_dataset(self, extracted_specimen: ExtractedSpecimen):
        # Arrange
        created_specimens: Dict[Union[str, SpecimenIdentifier], Specimen] = {
            extracted_specimen.identifier: extracted_specimen
        }
        method = SpecimenSamplingProcedureCode("Dissection")
        parent_identifier, parent_issuer = SpecimenIdentifier.get_identifier_and_issuer(
            extracted_specimen.identifier
        )
        dataset = SpecimenPreparationStep(
            "identifier",
            SpecimenSampling(
                method=method.code,
                parent_specimen_id=parent_identifier,
                parent_specimen_type=extracted_specimen.type.code,
            ),
            issuer_of_specimen_id=IssuerOfIdentifier("issuer"),
            processing_description="description",
        )

        # Act
        sampling = Sampling.from_dataset(dataset, created_specimens)

        # Assert
        assert sampling.method == method

    def test_processing_from_dataset(self):
        # Arrange
        method = SpecimenPreparationStepsCode("Specimen clearing")
        dataset = SpecimenPreparationStep(
            "identifier",
            SpecimenProcessing(
                description=method.code,
            ),
            issuer_of_specimen_id=IssuerOfIdentifier("issuer"),
        )

        # Act
        processing = Processing.from_dataset(dataset)

        # Assert
        assert processing.method == method

    def test_embedding_from_dataset(self):
        # Arrange
        medium = SpecimenEmbeddingMediaCode("Paraffin wax")
        dataset = SpecimenPreparationStep(
            "identifier",
            SpecimenProcessing(
                description="Embedding",
            ),
            embedding_medium=medium.code,
            issuer_of_specimen_id=IssuerOfIdentifier("issuer"),
        )

        # Act
        embedding = Embedding.from_dataset(dataset)

        # Assert
        assert embedding.medium == medium

    def test_fixation_from_dataset(self):
        # Arrange
        fixative = SpecimenFixativesCode("Neutral Buffered Formalin")
        dataset = SpecimenPreparationStep(
            "identifier",
            SpecimenProcessing(
                description="Fixation",
            ),
            fixative=fixative.code,
            issuer_of_specimen_id=IssuerOfIdentifier("issuer"),
        )

        # Act
        fixation = Fixation.from_dataset(dataset)

        # Assert
        assert fixation.fixative == fixative
