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

from typing import List, Sequence, Union
from pydicom import Dataset
import pytest
from highdicom import SpecimenDescription, SpecimenSampling, SpecimenStaining
from highdicom.content import (
    SpecimenCollection,
    SpecimenPreparationStep,
    SpecimenProcessing,
)
from pydicom.uid import UID
from pydicom.sr.coding import Code
from wsidicom.conceptcode import (
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenPreparationStepsCode,
    SpecimenStainsCode,
    SpecimenSamplingProcedureCode,
    AnatomicPathologySpecimenTypesCode,
)
from wsidicomizer.metadata.dicom_schema.sample import (
    CollectionDicom,
    EmbeddingDicom,
    FixationDicom,
    ProcessingDicom,
    SlideSampleDicom,
    StainingDicom,
)

from wsidicomizer.metadata.sample import (
    Collection,
    Embedding,
    ExtractedSpecimen,
    Fixation,
    Processing,
    Sample,
    SlideSample,
    SlideSamplePosition,
    Staining,
)


@pytest.fixture()
def specimen_id():
    yield "specimen"


@pytest.fixture()
def slide_sample_id():
    yield "slide sample"


@pytest.fixture()
def slide_sample_uid():
    yield UID("1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445424")


@pytest.fixture()
def specimen_type():
    yield AnatomicPathologySpecimenTypesCode("tissue specimen")


@pytest.fixture()
def collection_method():
    yield SpecimenCollectionProcedureCode("Excision")


@pytest.fixture()
def fixative():
    yield SpecimenFixativesCode("Neutral Buffered Formalin")


@pytest.fixture()
def specimen_sampling_method():
    yield SpecimenSamplingProcedureCode("Dissection")


@pytest.fixture()
def block_id():
    yield "block"


@pytest.fixture()
def embedding_medium():
    yield SpecimenEmbeddingMediaCode("Paraffin wax")


@pytest.fixture()
def block_sampling_method():
    yield SpecimenSamplingProcedureCode("Block sectioning")


@pytest.fixture()
def block_type():
    yield AnatomicPathologySpecimenTypesCode("tissue specimen")


@pytest.fixture()
def position():
    yield SlideSamplePosition(10, 20, 30)


@pytest.fixture()
def primary_anatomic_structures():
    yield [Code("value", "schema", "meaning")]


@pytest.fixture()
def stains():
    yield [
        SpecimenStainsCode("hematoxylin stain"),
        SpecimenStainsCode("water soluble eosin stain"),
    ]


def create_description(
    slide_sample_id: str,
    slide_sample_uid: UID,
    specimen_id: str,
    block_id: str,
    specimen_type: AnatomicPathologySpecimenTypesCode,
    collection_method: SpecimenCollectionProcedureCode,
    fixative: SpecimenFixativesCode,
    specimen_sampling_method: SpecimenSamplingProcedureCode,
    embedding_medium: SpecimenEmbeddingMediaCode,
    block_sampling_method: SpecimenSamplingProcedureCode,
    block_type: AnatomicPathologySpecimenTypesCode,
    position: SlideSamplePosition,
    primary_anatomic_structures: Sequence[Code],
    stains: Sequence[SpecimenStainsCode],
):
    collection = SpecimenPreparationStep(
        specimen_id,
        SpecimenCollection(collection_method.code),
    )
    fixation = SpecimenPreparationStep(
        specimen_id,
        SpecimenProcessing("Fixation"),
        fixative=fixative.code,
    )
    sampling_to_block = SpecimenPreparationStep(
        block_id,
        SpecimenSampling(
            specimen_sampling_method.code,
            specimen_id,
            specimen_type.code,
        ),
    )
    print("sampling to block", block_id, specimen_id)
    embedding = SpecimenPreparationStep(
        block_id,
        SpecimenProcessing("Embedding"),
        embedding_medium=embedding_medium.code,
    )
    sampling_to_slide = SpecimenPreparationStep(
        slide_sample_id,
        SpecimenSampling(
            block_sampling_method.code,
            block_id,
            block_type.code,
        ),
    )
    staining = SpecimenPreparationStep(
        slide_sample_id, SpecimenStaining([stain.code for stain in stains])
    )

    return SpecimenDescription(
        slide_sample_id,
        slide_sample_uid,
        position.to_tuple(),
        [
            collection,
            fixation,
            sampling_to_block,
            embedding,
            sampling_to_slide,
            staining,
        ],
        primary_anatomic_structures=primary_anatomic_structures,
    )


class TestSampleDicom:
    def test_collection_from_dataset(self):
        # Arrange
        method = SpecimenCollectionProcedureCode("Excision")
        dataset = SpecimenPreparationStep(
            "identifier",
            SpecimenCollection(
                procedure=method.code,
            ),
            processing_description="description",
        )

        # Act
        collection = CollectionDicom.from_dataset(dataset)

        # Assert
        assert collection.method == method

    def test_processing_from_dataset(self):
        # Arrange
        method = SpecimenPreparationStepsCode("Specimen clearing")
        dataset = SpecimenPreparationStep(
            "identifier",
            SpecimenProcessing(
                description=method.code,
            ),
        )

        # Act
        processing = ProcessingDicom.from_dataset(dataset)

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
        )

        # Act
        embedding = EmbeddingDicom.from_dataset(dataset)

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
        )

        # Act
        fixation = FixationDicom.from_dataset(dataset)

        # Assert
        assert fixation.fixative == fixative

    @pytest.mark.parametrize(
        "stains",
        [
            ["stain"],
            ["stain 1", "stain 2"],
            [SpecimenStainsCode("hematoxylin stain").code],
            [
                SpecimenStainsCode("hematoxylin stain").code,
                SpecimenStainsCode("water soluble eosin stain").code,
            ],
        ],
    )
    def test_staining_from_dataset(self, stains: List[Union[str, Code]]):
        # Arrange
        dataset = SpecimenPreparationStep("identifier", SpecimenStaining(stains))

        # Act
        staining = StainingDicom.from_dataset(dataset)

        # Assert
        assert staining.substances == stains

    @pytest.mark.parametrize(
        ["slide_sample_ids", "slide_sample_uids", "specimen_ids"],
        [
            [
                ["slide sample"],
                [
                    UID(
                        "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445424"
                    )
                ],
                ["specimen"],
            ],
            [
                ["slide sample 1", "slide sample 2"],
                [
                    UID(
                        "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445424"
                    ),
                    UID(
                        "1.2.826.0.1.3680043.8.498.11522107373528810886192809691753445425"
                    ),
                ],
                ["specimen 1", "specimen 2"],
            ],
        ],
    )
    def test_slide_sample_from_dataset(
        self,
        slide_sample_ids: Sequence[str],
        slide_sample_uids: Sequence[UID],
        specimen_ids: Sequence[str],
        block_id: str,
        specimen_type: AnatomicPathologySpecimenTypesCode,
        collection_method: SpecimenCollectionProcedureCode,
        fixative: SpecimenFixativesCode,
        specimen_sampling_method: SpecimenSamplingProcedureCode,
        embedding_medium: SpecimenEmbeddingMediaCode,
        block_sampling_method: SpecimenSamplingProcedureCode,
        block_type: AnatomicPathologySpecimenTypesCode,
        position: SlideSamplePosition,
        primary_anatomic_structures: Sequence[Code],
        stains: Sequence[SpecimenStainsCode],
    ):
        # Arrange
        descriptions: List[SpecimenDescription] = []
        dataset = Dataset()
        for slide_sample_id, slide_sample_uid, specimen_id in zip(
            slide_sample_ids, slide_sample_uids, specimen_ids
        ):
            description = create_description(
                slide_sample_id,
                slide_sample_uid,
                specimen_id,
                block_id,
                specimen_type,
                collection_method,
                fixative,
                specimen_sampling_method,
                embedding_medium,
                block_sampling_method,
                block_type,
                position,
                primary_anatomic_structures,
                stains,
            )

            descriptions.append(description)
        dataset.SpecimenDescriptionSequence = descriptions

        # Act
        slide_samples, stainings = SlideSampleDicom.from_dataset(descriptions)

        # Assert
        assert slide_samples is not None
        assert stainings is not None
        assert len(slide_samples) == len(slide_sample_ids)
        for slide_sample_index, slide_sample in enumerate(slide_samples):
            assert isinstance(slide_sample, SlideSample)
            assert slide_sample.identifier == slide_sample_ids[slide_sample_index]
            assert slide_sample.uid == slide_sample_uids[slide_sample_index]
            # assert slide_sample.anatomical_sites == primary_anatomic_structures
            # assert slide_sample.position == position
            assert slide_sample.sampled_from is not None
            assert slide_sample.sampled_from.method == block_sampling_method
            block = slide_sample.sampled_from.specimen
            assert isinstance(block, Sample)
            assert block.identifier == block_id
            assert block.type == block_type
            embedding_step = block.steps[0]
            assert isinstance(embedding_step, Embedding)
            assert embedding_step.medium == embedding_medium
            assert len(block.sampled_from) == len(specimen_ids)
            for index, specimen_id in enumerate(specimen_ids):
                assert block.sampled_from[index].method == specimen_sampling_method
                specimen = block.sampled_from[index].specimen
                assert isinstance(specimen, ExtractedSpecimen)
                assert specimen.identifier == specimen_id
                assert specimen.type == specimen_type
                fixation_step = specimen.steps[1]
                assert isinstance(fixation_step, Fixation)
                assert fixation_step.fixative == fixative
                collection_step = specimen.steps[0]
                assert isinstance(collection_step, Collection)
                assert collection_step.method == collection_method
