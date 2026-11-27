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

"""Source for reading CZI files with pylibCZIrw."""

from contextlib import ExitStack
from functools import cached_property
from pathlib import Path
from threading import RLock
from typing import Any

from pydicom import Dataset
from pylibCZIrw import czi as pylib_czi  # pyright: ignore[reportMissingImports]
from upath import UPath
from wsidicom.codec import Encoder
from wsidicom.codec.settings import Channels, Jpeg2kSettings, JpegSettings
from wsidicom.metadata import UidGenerator, WsiMetadata
from wsidicom.paths import as_local_path

from wsidicomizer.config import get_settings
from wsidicomizer.dicomizer_source import DicomizerSource, PyramidLevel
from wsidicomizer.image_data import BaseDicomizerImageData
from wsidicomizer.metadata import (
    MetadataPostProcessor,
    MetadataPreProcessor,
)
from wsidicomizer.sources.czirw.czirw_image_data import (
    PIXEL_TYPES,
    CziRwImageData,
    CziRwLayout,
)
from wsidicomizer.sources.czirw.czirw_metadata import CziRwMetadata


class CziRwSource(DicomizerSource):
    """Read CZI image regions and pyramid levels through pylibCZIrw."""

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
        optimize: bool = False,
    ) -> None:
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
        self._optimize = optimize
        local_filepath = self._require_local_filepath(filepath)
        with ExitStack() as stack:
            reader = stack.enter_context(pylib_czi.open_czi(str(local_filepath)))
            self._layout = self._inspect_reader(reader)
            self._reader = reader
            self._base_metadata = CziRwMetadata(
                reader.raw_metadata, self._layout.channel_count
            )
            self._reader_stack = stack.pop_all()
        if self._tile_size is None:
            self._tile_size = get_settings().default_tile_size
        self._read_lock = RLock()
        self._focal_plane_to_index = {
            focal_plane: self._layout.z_start + index
            for index, focal_plane in enumerate(self._layout.focal_planes)
        }
        self._channel_to_index = {
            str(index + 1): self._layout.channel_start + index
            for index in range(self._layout.channel_count)
        }

    @property
    def _pixel_format(self) -> tuple[Channels, int]:
        samples_per_pixel, dtype = PIXEL_TYPES[self._layout.pixel_type]
        return self._pixel_format_from(samples_per_pixel, dtype)

    @cached_property
    def _encoder(self) -> Encoder:
        if self._provided_encoder is not None:
            return self._provided_encoder
        channels, bits = self._pixel_format
        if self._optimize and bits <= 8:
            settings = (
                JpegSettings(channels=channels, optimize=True)
                if channels == Channels.GRAYSCALE
                else JpegSettings(optimize=True)
            )
            return Encoder.create_for_settings(settings)
        return self._default_encoder(channels, bits)

    @staticmethod
    def _default_encoder(channels: Channels, bits: int = 8) -> Encoder:
        if bits > 8:
            return Encoder.create_for_settings(
                Jpeg2kSettings(bits=bits, channels=channels)
            )
        return DicomizerSource._default_encoder(channels, bits)

    @property
    def pyramid_levels(self) -> list[PyramidLevel]:
        return [
            PyramidLevel(0, level, level) for level in range(len(self._layout.zooms))
        ]

    @property
    def base_metadata(self) -> CziRwMetadata:
        return self._base_metadata

    @staticmethod
    def is_supported(
        path: str | Path | UPath, file_options: dict[str, Any] | None = None
    ) -> bool:
        local_filepath = as_local_path(path)
        if local_filepath is None:
            return False
        try:
            with pylib_czi.open_czi(str(local_filepath)) as reader:
                CziRwSource._inspect_reader(reader)
        except Exception:
            return False
        return True

    def close(self) -> None:
        self._reader_stack.close()

    def _create_level_image_data(self, level_index: int) -> BaseDicomizerImageData:
        if level_index < 0 or level_index >= len(self._layout.zooms):
            raise ValueError(f"CZI pyramid level {level_index} is not available.")
        return CziRwImageData(
            reader=self._reader,
            layout=self._layout,
            encoder=self._encoder,
            level_index=level_index,
            tile_size=self._tile_size,
            read_lock=self._read_lock,
            channel_to_index=self._channel_to_index,
            focal_plane_to_index=self._focal_plane_to_index,
            image_metadata=self.metadata.pyramid.image,
        )

    def _create_label_image_data(self) -> BaseDicomizerImageData | None:
        return None

    def _create_overview_image_data(self) -> BaseDicomizerImageData | None:
        return None

    def _create_thumbnail_image_data(self) -> BaseDicomizerImageData | None:
        return None

    @classmethod
    def _inspect_reader(cls, reader: Any) -> CziRwLayout:
        bounds = reader.total_bounding_box_no_pyramid
        x_start, x_end = bounds["X"]
        y_start, y_end = bounds["Y"]
        c_start, c_end = bounds["C"]
        z_start, z_end = bounds["Z"]
        t_start, t_end = bounds["T"]
        if t_end - t_start != 1:
            raise ValueError("CZI time series are not supported.")

        unsupported_axes = [
            axis
            for axis, (start, end) in bounds.items()
            if axis not in {"X", "Y", "C", "Z", "T"} and end - start > 1
        ]
        if unsupported_axes:
            raise ValueError(
                f"CZI dimensions {', '.join(unsupported_axes)} are not supported."
            )

        channel_count = c_end - c_start
        z_count = z_end - z_start
        if channel_count < 1 or z_count < 1 or x_end <= x_start or y_end <= y_start:
            raise ValueError("CZI image dimensions are invalid.")

        scene_rectangles = list(reader.scenes_bounding_rectangle_no_pyramid.values())
        for index, first in enumerate(scene_rectangles):
            for second in scene_rectangles[index + 1 :]:
                overlaps = (
                    first.x < second.x + second.w
                    and second.x < first.x + first.w
                    and first.y < second.y + second.h
                    and second.y < first.y + first.h
                )
                if overlaps:
                    raise ValueError("Overlapping CZI scenes cannot be combined.")

        pixel_types = {
            reader.get_channel_pixel_type(channel) for channel in range(c_start, c_end)
        }
        if len(pixel_types) != 1:
            raise ValueError("CZI channels with different pixel types are unsupported.")
        pixel_type = pixel_types.pop()
        if pixel_type not in PIXEL_TYPES:
            raise ValueError(f"CZI pixel type {pixel_type} is unsupported.")

        metadata = CziRwMetadata(reader.raw_metadata, channel_count)
        focal_planes = metadata.focal_plane_mapping
        if len(focal_planes) != z_count or len(set(focal_planes)) != z_count:
            raise ValueError(
                "CZI z planes require unique physical positions in the metadata."
            )

        zooms: set[float] = set()

        def collect_zoom(index: int, subblock: Any) -> bool:
            zoom = float(subblock.get_zoom())
            if 0 < zoom <= 1:
                zooms.add(round(zoom, 8))
            return True

        reader.enumerate_subblocks(collect_zoom)
        zooms.add(1.0)
        return CziRwLayout(
            x=x_start,
            y=y_start,
            width=x_end - x_start,
            height=y_end - y_start,
            channel_start=c_start,
            channel_count=channel_count,
            z_start=z_start,
            z_count=z_count,
            pixel_type=pixel_type,
            focal_planes=tuple(focal_planes),
            zooms=tuple(sorted(zooms, reverse=True)),
        )


__all__ = ["CziRwSource"]
