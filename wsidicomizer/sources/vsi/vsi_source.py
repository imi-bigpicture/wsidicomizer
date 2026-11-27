#    Copyright 2026 SECTRA AB
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

"""Source for reading Olympus VSI file."""

import logging
import math
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
from pydicom import Dataset
from tifffile import TiffFile
from upath import UPath
from wsidicom.codec import Encoder
from wsidicom.codec.settings import Channels
from wsidicom.metadata import (
    ImageCoordinateSystem,
    UidGenerator,
    WsiMetadata,
)
from wsidicom.paths import as_local_path

from wsidicomizer.dicomizer_source import DicomizerSource, PyramidLevel
from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.metadata import MetadataPostProcessor, MetadataPreProcessor
from wsidicomizer.sources.vsi.ets import EtsFile
from wsidicomizer.sources.vsi.vsi_image_data import TileFormat, VsiLevelImageData
from wsidicomizer.sources.vsi.vsi_metadata import (
    LABEL_NAME,
    OVERVIEW_NAME,
    VsiMetadata,
    VsiTagReader,
)

MINIMUM_ASSOCIATED_WIDTH = 1024
"""Smallest width to pick a pyramid level of an associated image by."""


class VsiSource(DicomizerSource):
    """Source for an Olympus VSI slide.

    A VSI slide is a `.vsi` TIFF holding the metadata and a sidecar directory of
    `.ets` containers holding the pyramids. The pyramid tiles are JPEG 2000 or
    JPEG codestreams of uniform size without overlap and are passed through to
    DICOM unchanged.
    """

    def __init__(
        self,
        filepath: UPath,
        encoder: Encoder | None,
        tile_size: int | None = None,
        metadata: WsiMetadata | None = None,
        default_metadata: WsiMetadata | None = None,
        include_confidential: bool = True,
        metadata_post_processor: Dataset | MetadataPostProcessor | None = None,
        metadata_pre_processor: MetadataPreProcessor | None = None,
        uid_generator: UidGenerator | None = None,
        file_options: dict[str, Any] | None = None,
    ) -> None:
        """Create a new VsiSource.

        Parameters
        ----------
        filepath: UPath
            Path to the `.vsi` file.
        encoder: Encoder | None
            Encoder to use. Only used for blank frames, as the pyramid is passed
            through. If None, the source picks a default matching its pixel
            format.
        tile_size: Optional[int] = None,
            Ignored, as the tile size of the file is used.
        metadata: Optional[WsiMetadata] = None
            User-specified metadata that will overload metadata from source image file.
        default_metadata: Optional[WsiMetadata] = None
            User-specified metadata that will be used as default values.
        include_confidential: bool = True
            Include confidential metadata.
        metadata_post_processor: Optional[Union[Dataset, MetadataPostProcessor]] = None
            Optional metadata post processing by update from dataset or callback.
        metadata_pre_processor: MetadataPreProcessor | None = None
            Optional metadata pre processing by callback, of the metadata read
            from the file before `metadata` and `default_metadata` are merged
            into it.
        uid_generator: UidGenerator | None = None
            Generator used by the source to fill metadata UIDs. `None` uses the
            default `CallableUidGenerator` backed by `pydicom.generate_uid`.
        file_options: dict[str, Any] | None = None
            Options forwarded to the fsspec filesystem when reading a fsspec
            path. Ignored, as only local files are read.
        """
        super().__init__(
            filepath=filepath,
            encoder=encoder,
            tile_size=tile_size,
            metadata=metadata,
            default_metadata=default_metadata,
            include_confidential=include_confidential,
            metadata_post_processor=metadata_post_processor,
            metadata_pre_processor=metadata_pre_processor,
            uid_generator=uid_generator,
        )
        local_filepath = self._require_local_filepath(filepath)
        self._tiff = TiffFile(local_filepath)
        try:
            tag_reader = VsiTagReader(local_filepath)
            self._images = {image.name: image for image in tag_reader.read_images()}
            self._stacks = self._open_stacks(local_filepath, list(self._images))
            self._areas = {
                name: stack
                for name, stack in self._stacks.items()
                if name not in (LABEL_NAME, OVERVIEW_NAME)
            } or dict(self._stacks)
            self._ets = max(
                self._areas.values(), key=lambda stack: stack.tiled_sizes[0].area
            )
        except Exception:
            self._tiff.close()
            raise
        self._base_metadata = VsiMetadata(
            self._tiff,
            self._ets.image_size or self._ets.tiled_sizes[0] * self._ets.tile_size,
            self._images.get(self._name_of(self._ets)),
            tag_reader.read_slide_identifier(),
            tag_reader.read_creation_time(),
        )

    def close(self) -> None:
        for stack in self._stacks.values():
            stack.close()
        self._tiff.close()

    @property
    def base_metadata(self) -> VsiMetadata:
        return self._base_metadata

    @property
    def pyramid_levels(self) -> list[PyramidLevel]:
        # A slide with several scanned areas holds several pyramids. Converting more
        # than one is not supported yet, so fail loudly rather than emitting a
        # multi-pyramid file. The areas are still individually readable (metadata,
        # tiles, associated images); only assembling the conversion is refused.
        if len(self._areas) > 1:
            raise NotImplementedError(
                f"Slide has {len(self._areas)} scanned areas (pyramids); only one is "
                "supported."
            )
        return [
            PyramidLevel(pyramid, level, index)
            for index, (pyramid, _, _, level) in enumerate(self._area_levels)
        ]

    @cached_property
    def _area_levels(self) -> list[tuple[int, str, EtsFile, int]]:
        """The levels of every scanned area, as (pyramid, name, stack, level).

        A slide can hold several scanned areas, each a pyramid of its own at its
        own position on the slide.
        """
        return [
            (pyramid, name, stack, level)
            for pyramid, (name, stack) in enumerate(self._areas.items())
            for level in range(len(stack.tiled_sizes))
        ]

    @property
    def _pixel_format(self) -> tuple[Channels, int]:
        tile_format = TileFormat.from_ets(self._ets, 0)
        return self._pixel_format_from(
            tile_format.samples_per_pixel, np.dtype(f"u{tile_format.bits // 8}")
        )

    @staticmethod
    def is_supported(
        path: str | Path | UPath, file_options: dict[str, Any] | None = None
    ) -> bool:
        local_filepath = as_local_path(path)
        if local_filepath is None:
            return False
        return len(VsiSource._get_stack_files(local_filepath)) > 0

    def _create_level_image_data(self, level_index: int) -> BaseDicomizerImageData:
        _, name, stack, level = self._area_levels[level_index]
        return self._create_area_image_data(name, stack, level)

    def _create_area_image_data(
        self, name: str, stack: EtsFile, level: int
    ) -> BaseDicomizerImageData:
        """Return image data for a level of a scanned area."""
        image = self._images.get(name)
        is_converted_pyramid = stack is self._ets
        if is_converted_pyramid:
            # Keep any user-specified metadata for the pyramid the metadata
            # was merged for.
            pixel_spacing = self.metadata.pyramid.image.pixel_spacing
            image_coordinate_system = (
                self.metadata.pyramid.image.image_coordinate_system
            )
        else:
            pixel_spacing = image.pixel_spacing if image else None
            image_coordinate_system = (
                ImageCoordinateSystem(image.origin, rotation=0)
                if image is not None and image.origin is not None
                else None
            )
        return VsiLevelImageData(
            stack, level, self._encoder, pixel_spacing, image_coordinate_system
        )

    def _name_of(self, stack: EtsFile) -> str:
        """Return the name the `.vsi` gives a stack."""
        return next(name for name, opened in self._stacks.items() if opened is stack)

    def _create_label_image_data(self) -> BaseDicomizerImageData | None:
        return self._create_associated_image_data(LABEL_NAME)

    def _create_overview_image_data(self) -> BaseDicomizerImageData | None:
        return self._create_associated_image_data(OVERVIEW_NAME)

    def _create_thumbnail_image_data(self) -> BaseDicomizerImageData | None:
        return None

    def _create_associated_image_data(self, name: str) -> BaseDicomizerImageData | None:
        """Return image data for the label or macro image, if the slide has one."""
        stack = self._stacks.get(name)
        if stack is None:
            return None
        image = self._images.get(name)
        level = self._select_associated_level(stack)
        return VsiLevelImageData(
            stack,
            level,
            self._encoder,
            image.pixel_spacing if image else None,
            ImageCoordinateSystem(image.origin, rotation=0)
            if image is not None and image.origin is not None
            else None,
        )

    @staticmethod
    def _select_associated_level(stack: EtsFile) -> int:
        """Return the level to use for an associated image.

        The label and macro are full pyramids of their own, and their base level
        is needlessly large for a label image. The smallest level that is still
        at least `MINIMUM_ASSOCIATED_WIDTH` wide is used, which keeps the tiles
        a copy of stored tiles instead of a resampling.
        """
        base_size = stack.image_size or stack.tiled_sizes[0] * stack.tile_size
        return max(
            (
                level
                for level in range(len(stack.tiled_sizes))
                if math.ceil(base_size.width / 2**level) >= MINIMUM_ASSOCIATED_WIDTH
            ),
            default=0,
        )

    @classmethod
    def _open_stacks(cls, filepath: Path, names: list[str]) -> dict[str, EtsFile]:
        """Open the `.ets` stacks of the slide, keyed by the name the `.vsi`
        gives them.

        The names are listed in the same order as the stacks, so they are zipped
        together. If the two do not line up the names are dropped rather than
        risking a label being converted as the slide image, and the stacks are
        keyed by their directory name instead.
        """
        stack_files = cls._get_stack_files(filepath)
        if len(stack_files) == 0:
            raise ValueError(f"No .ets pyramid found for {filepath}.")
        if len(names) != len(stack_files):
            logging.warning(
                "Found %d image names for %d stacks in %s, ignoring the names.",
                len(names),
                len(stack_files),
                filepath,
            )
            names = [stack_file.parent.name for stack_file in stack_files]
        return {
            name: EtsFile(path) for name, path in zip(names, stack_files, strict=True)
        }

    @staticmethod
    def _get_stack_files(filepath: Path) -> list[Path]:
        """Return one pyramid `.ets` file per stack of the sidecar directory.

        Matched by the `frame_t` name, as the sidecar also holds non-image
        `blob_*.ets` property streams. A stack normally has a single
        `frame_t.ets` (or `frame_t_0.ets` when it has extra dimensions); the
        `_N` suffix would index time points, of which only the first is taken,
        so a stack still maps to a single pyramid.
        """
        if filepath.suffix.lower() != ".vsi" or not filepath.is_file():
            return []
        sidecar = filepath.parent.joinpath(f"_{filepath.stem}_")
        if not sidecar.is_dir():
            return []
        by_stack: dict[Path, Path] = {}
        for path in sorted(sidecar.glob("*/frame_t*.ets")):
            if path.parent not in by_stack and EtsFile.is_ets(path):
                by_stack[path.parent] = path
        return [by_stack[stack] for stack in sorted(by_stack)]
