#    Copyright 2021, 2022, 2023 SECTRA AB
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

"""Module containing a base Source implementation suitable for use with non-DICOM
files."""

from abc import ABCMeta, abstractmethod
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from functools import cached_property
from importlib.metadata import version
from pathlib import Path

import numpy as np
from pydicom import Dataset, config
from wsidicom import ImageData
from wsidicom.codec import Encoder, Jpeg2kSettings, JpegSettings
from wsidicom.codec.settings import Channels
from wsidicom.conceptcode import ContributingEquipmentPurposeCode
from wsidicom.graphical_annotations import AnnotationInstance
from wsidicom.instance import WsiDataset, WsiInstance
from wsidicom.metadata import (
    CallableUidGenerator,
    ContributingEquipment,
    ImageType,
    UidGenerator,
    WsiMetadata,
)
from wsidicom.metadata.sample import SlideSample
from wsidicom.metadata.schema.dicom import WsiMetadataDicomSchema
from wsidicom.source import Source

from wsidicomizer.config import get_settings
from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor, WsiDicomizerMetadata
from wsidicomizer.uid_resolver import MetadataUidResolver

config.enforce_valid_values = True
config.future_behavior()


class DicomizerSource(Source, metaclass=ABCMeta):
    """
    Metaclass for Dicomizer sources. Subclasses should implement the method
    is_supported(), _create_level_image_data(), _create_label_image_data(), and
     _create_overview_image_data() and the properties metadata, pyramid_levels.
     Subclasses can override the __init__().
    """

    _instance_cls: type[WsiInstance] = WsiInstance

    def __init__(
        self,
        filepath: Path,
        encoder: Encoder | None,
        tile_size: int | None = None,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        uid_generator: UidGenerator | None = None,
    ) -> None:
        """Create a new DicomizerSource.

        Parameters
        ----------
        filepath: Path
            Path to the file.
        encoder: Encoder | None
            Encoder to use. Pyramid is always re-encoded using the encoder.
            If None, the source picks a default matching its pixel format.
        tile_size: Optional[int]
            Tile size to use. If None, the default tile size is used.
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        include_confidential: bool = True
            Include confidential metadata.
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None
            Optional metadata post processing by update from dataset or callback.
        uid_generator: UidGenerator | None = None
            Generator used by the source to fill metadata UIDs. `None` uses
            the default `CallableUidGenerator` backed by
            `pydicom.generate_uid`.
        """
        self._filepath: Path | None = filepath
        self._provided_encoder = encoder
        self._tile_size = tile_size
        self._user_metadata = metadata
        self._default_metadata = default_metadata
        self._include_confidential = include_confidential
        self._metadata_post_processor = metadata_post_processor
        self._uid_generator: UidGenerator = uid_generator or CallableUidGenerator()

    @cached_property
    def _encoder(self) -> Encoder:
        """The encoder to use, resolving a format-matched default when none was
        supplied."""
        if self._provided_encoder is not None:
            return self._provided_encoder
        return self._default_encoder(*self._pixel_format)

    @property
    @abstractmethod
    def _pixel_format(self) -> tuple[Channels, int]:
        """The (channels, bits) the source produces, used to pick a default
        encoder when none is supplied. Derive it from a sample count and dtype
        with ``_pixel_format_from``."""
        raise NotImplementedError()

    @staticmethod
    def _pixel_format_from(
        samples_per_pixel: int, dtype: np.typing.DTypeLike
    ) -> tuple[Channels, int]:
        """Map a sample count and numpy dtype to (channels, bits)."""
        channels = Channels.GRAYSCALE if samples_per_pixel == 1 else Channels.RGB
        return channels, np.dtype(dtype).itemsize * 8

    @staticmethod
    def _default_encoder(channels: Channels, bits: int = 8) -> Encoder:
        """Create a default encoder for a pixel format.

        Always compressed (uncompressed WSI is prohibitively large) using the
        most broadly supported codec for the depth: 8-bit uses JPEG, deeper
        greyscale uses JPEG 2000 (JPEG is 8-bit only). RGB keeps the historical
        bare ``JpegSettings`` default (YBR).
        """
        if channels == Channels.GRAYSCALE:
            if bits > 8:
                settings = Jpeg2kSettings(bits=bits, channels=channels)
            else:
                settings = JpegSettings(channels=channels)
            return Encoder.create_for_settings(settings)
        return Encoder.create_for_settings(JpegSettings())

    @staticmethod
    @abstractmethod
    def is_supported(path: Path) -> bool:
        """Return True if file in filepath is supported by Dicomizer."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def base_metadata(self) -> WsiDicomizerMetadata:
        """Return metadata for file."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def pyramid_levels(self) -> dict[tuple[int, float, str], int]:
        """Dictionary of pyramid level (scalings), focal plane, and optical path as key
        and level index in file as value for levels in file."""
        raise NotImplementedError()

    @abstractmethod
    def _create_level_image_data(self, level_index: int) -> BaseDicomizerImageData:
        """Return image data instance for level."""
        raise NotImplementedError()

    @abstractmethod
    def _create_label_image_data(self) -> BaseDicomizerImageData | None:
        """Return image data instance for label."""
        raise NotImplementedError()

    @abstractmethod
    def _create_overview_image_data(self) -> BaseDicomizerImageData | None:
        """Return image data instance for overview."""
        raise NotImplementedError()

    @abstractmethod
    def _create_thumbnail_image_data(self) -> BaseDicomizerImageData | None:
        """Return image data instance for thumbnail."""
        raise NotImplementedError()

    @cached_property
    def metadata(self) -> WsiMetadata:
        """Merged metadata from source file with user-specified and default metadata,
        with added required content and resolved UIDs."""
        merged = self.base_metadata.merge(
            self.user_metadata,
            self.default_metadata,
            self._include_confidential,
        )
        merged = self._ensure_required_content(merged)
        merged = self._add_contributing_equipment(merged)
        return MetadataUidResolver(self._uid_generator).resolve(merged)

    @staticmethod
    def _add_contributing_equipment(metadata: WsiMetadata) -> WsiMetadata:
        """Record wsidicomizer as contributing (modifying) equipment, so the
        converted file documents that it was produced by a tool rather than
        acquired directly by the scanner. Appended, preserving any existing items.
        """
        wsidicomizer_equipment = ContributingEquipment(
            purpose=ContributingEquipmentPurposeCode("Modifying Equipment"),
            manufacturer="wsidicomizer",
            model_name="wsidicomizer",
            software_versions=[version("wsidicomizer")],
            description="Converted to DICOM WSI by wsidicomizer",
            contribution_datetime=datetime.now(),
        )
        return replace(
            metadata,
            contributing_equipment=[
                *metadata.contributing_equipment,
                wsidicomizer_equipment,
            ],
        )

    @staticmethod
    def _ensure_required_content(metadata: WsiMetadata) -> WsiMetadata:
        """Populate Type-1 structural content the resolver does not synthesize.

        Specifically `Slide.samples`: wsidicom's `SpecimenDescriptionSequence` is
        Type 1 with VM >= 1, so at least one `SlideSample` must be present
        before the metadata is dumped. The UID resolver then fills the
        per-sample uid.
        """
        DEFAULT_SLIDE_SAMPLE_IDENTIFIER = "Unknown"

        if metadata.slide.samples is not None and len(metadata.slide.samples) > 0:
            return metadata
        slide = replace(
            metadata.slide,
            samples=[SlideSample(identifier=DEFAULT_SLIDE_SAMPLE_IDENTIFIER)],
        )
        metadata = replace(metadata, slide=slide)
        return metadata

    @property
    def user_metadata(self) -> WsiMetadata | None:
        return self._user_metadata

    @property
    def default_metadata(self) -> WsiMetadata | None:
        return self._default_metadata

    @property
    def base_dataset(self) -> WsiDataset:
        return self.level_instances[0].dataset

    @cached_property
    def level_instances(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
    ) -> list[WsiInstance]:
        return [
            self._create_instance(
                self._create_level_image_data(level_index),
                ImageType.VOLUME,
                pyramid_index,
            )
            for (
                pyramid_index,
                _,
                _,
            ), level_index in self.pyramid_levels.items()
        ]

    @cached_property
    def label_instances(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
    ) -> list[WsiInstance]:
        label = self._create_label_image_data()
        if label is None:
            return []
        return [self._create_instance(label, ImageType.LABEL)]

    @cached_property
    def overview_instances(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
    ) -> list[WsiInstance]:
        overview = self._create_overview_image_data()
        if overview is None:
            return []
        return [self._create_instance(overview, ImageType.OVERVIEW)]

    @cached_property
    def thumbnail_instances(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
    ) -> list[WsiInstance]:
        thumbnail = self._create_thumbnail_image_data()
        if thumbnail is None:
            return []
        return [self._create_instance(thumbnail, ImageType.THUMBNAIL)]

    @property
    def annotation_instances(self) -> list[AnnotationInstance]:
        return []

    def _create_instance(
        self,
        image_data: ImageData,
        image_type: ImageType,
        pyramid_index: int | None = None,
    ) -> WsiInstance:
        """Create instance from image data using this source's ``_instance_cls``."""
        dataset = self._create_dataset(
            image_type, image_data.photometric_interpretation
        )
        return self._instance_cls.create_instance(
            image_data, dataset, image_type, pyramid_index
        )

    def _create_dataset(
        self, image_type: ImageType, photometric_interpretation: str
    ) -> WsiDataset:
        require_icc_profile = (
            get_settings().insert_icc_profile_if_missing
            and not photometric_interpretation.startswith("MONOCHROME")
        )
        dataset = WsiMetadataDicomSchema().dump(
            self.metadata, image_type, require_icc_profile
        )
        if isinstance(self._metadata_post_processor, Dataset):
            dataset.update(self._metadata_post_processor)
        elif callable(self._metadata_post_processor):
            dataset = self._metadata_post_processor(dataset, self.metadata)
        return WsiDataset(dataset)

    @staticmethod
    def _is_included_level(
        level: int,
        present_levels: Sequence[int],
        include_indices: Sequence[int] | None = None,
    ) -> bool:
        """Return true if pyramid level is in included levels.

        Parameters
        ----------
        level: int
            Pyramid level to check.
        present_levels: Sequence[int]
            List of pyramid levels present.
        include_indices: Optional[Sequence[int]] = None
            Optional list indices (in present levels) to include, e.g. [0, 1]
            includes the two lowest levels. Negative indices can be used,
            e.g. [-1, -2] includes the two highest levels. Default of None
            will not limit the selection. An empty sequence will excluded all
            levels.

        Returns
        ----------
        bool
            True if level should be included.
        """
        if level not in present_levels:
            return False
        if include_indices is None:
            return True
        absolute_levels = [
            present_levels[level]
            for level in include_indices
            if -len(present_levels) <= level < len(present_levels)
        ]
        return level in absolute_levels
