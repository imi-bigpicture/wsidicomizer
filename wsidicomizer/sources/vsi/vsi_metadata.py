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

"""Metadata for Olympus VSI file, read from the TIFF tags of the `.vsi`."""

import logging
import struct
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from tifffile import TiffFile, TiffPage
from wsidicom.geometry import PointMm, Size, SizeMm
from wsidicom.metadata import (
    Equipment,
    Image,
    ImageCoordinateSystem,
    Pyramid,
    Slide,
)

from wsidicomizer.metadata import WsiDicomizerMetadata
from wsidicomizer.wsi_format import FormatCoordinateDefaults, WsiFormat

MAKE_TAG = 271
MODEL_TAG = 272
DATETIME_TAG = 306
OLYMPUS_SIS_TAG = 33560
EXIF_TAG = 34665
SAMPLE_MASK_NAME = "Sample Mask"
FOCUS_MAP_NAME_SUFFIX = "FocusMap"

LABEL_NAME = "Label"
OVERVIEW_NAME = "Overview"
"""Names the scanner gives the label and macro image."""

_ORIGIN_TAG = 2018
_PHYSICAL_SIZE_TAG = 2019
_CALIBRATION_UNIT_TAG = 2020
_NAME_TAG = 2030
_SLIDE_NAME_TAG = 2061
_UNICODE_TYPE = 0x2000
_DOUBLE_2_TYPE = 0x104
_TLV_HEADER = struct.Struct("<4I")
_PAIR = struct.Struct("<2d")
_MICROMETERS = "10^-6m^1"
_NOT_AN_IMAGE = (SAMPLE_MASK_NAME, FOCUS_MAP_NAME_SUFFIX, "FocusPoints")
"""Named entries that describe a `.vsi` page or a focus grid, not a pyramid."""


@dataclass(frozen=True)
class VsiImage:
    """An image described by the VSI metadata blocks.

    The blocks are a tag/length/value tree of
    `[u32 fieldType][u32 tag][u32 ...][u32 dataSize][data]` records. The tree
    structure is not needed to read the per-image fields, as each belongs to the
    name record that follows it: name (tag 2030, UTF-16), position of the image
    on the slide (2018, two doubles), physical pixel size (2019, two doubles)
    and the unit of both (2020, a string such as `10^-6m^1`).
    """

    name: str
    origin: PointMm | None
    """Position of the top left corner of the image on the slide."""
    pixel_spacing: SizeMm | None

    @classmethod
    def read_all(cls, filepath: Path) -> list["VsiImage"]:
        """Return the images the `.vsi` describes, in file order.

        Entries that name a sample mask or a focus grid rather than a pyramid
        are left out; the rest match the `.ets` stacks of the slide one to one,
        in the same order, on every slide examined.
        """
        data = filepath.read_bytes()
        origins = cls._read_pairs(data, _ORIGIN_TAG)
        physical_sizes = cls._read_pairs(data, _PHYSICAL_SIZE_TAG)
        scale = cls._read_scale_to_mm(data)
        images: list[VsiImage] = [
            cls(
                name,
                cls._pair_before(origins, offset, scale, PointMm),
                cls._pair_before(physical_sizes, offset, scale, SizeMm),
            )
            for offset, name in cls._read_strings(data, _NAME_TAG)
            if not name.endswith(_NOT_AN_IMAGE)
        ]
        return cls._move_onto_slide(images)

    @staticmethod
    def read_slide_identifier(filepath: Path) -> str | None:
        """Return the slide name / barcode string (tag 2061), or None if absent.

        Optional in the file - present as a real slide-label barcode on some
        slides (`04050732B0018S`), a short name on others, and missing on
        others. Confirmed against Olympus's OlyVIA viewer, which shows it as
        `Slide Name`.
        """
        strings = VsiImage._read_strings(filepath.read_bytes(), _SLIDE_NAME_TAG)
        return strings[0][1] if strings else None

    @staticmethod
    def _read_strings(data: bytes, tag: int) -> list[tuple[int, str]]:
        """Return the offset and value of each UTF-16 record with a tag."""
        strings = []
        for offset, size in VsiImage._find_records(data, tag):
            field_type = _TLV_HEADER.unpack_from(data, offset)[0]
            if field_type & 0xFFFFFF != _UNICODE_TYPE or size % 2 or size > 512:
                continue
            try:
                value = data[
                    offset + _TLV_HEADER.size : offset + _TLV_HEADER.size + size
                ].decode("utf-16-le")
            except UnicodeDecodeError:
                continue
            if value.isprintable():
                strings.append((offset, value))
        return strings

    @staticmethod
    def _read_pairs(data: bytes, tag: int) -> list[tuple[int, tuple[float, float]]]:
        """Return the offset and value of each pair-of-doubles record for a tag."""
        return [
            (offset, _PAIR.unpack_from(data, offset + _TLV_HEADER.size))
            for offset, size in VsiImage._find_records(data, tag)
            if size == _PAIR.size
            and _TLV_HEADER.unpack_from(data, offset)[0] == _DOUBLE_2_TYPE
        ]

    @staticmethod
    def _find_records(data: bytes, tag: int):
        """Yield the offset and data size of each record with a tag."""
        needle = struct.pack("<I", tag)
        position = data.find(needle)
        while position != -1:
            offset = position - 4
            if offset >= 0:
                size = _TLV_HEADER.unpack_from(data, offset)[3]
                if 0 < size <= 4096 and offset + _TLV_HEADER.size + size <= len(data):
                    yield offset, size
            position = data.find(needle, position + 1)

    @staticmethod
    def _pair_before(
        records: list[tuple[int, tuple[float, float]]],
        offset: int,
        scale: float | None,
        factory: Callable[[float, float], Any],
    ):
        """Return the value of the last record before an offset, scaled to mm."""
        values = [value for record_offset, value in records if record_offset < offset]
        if not values or scale is None:
            return None
        return factory(values[-1][0] * scale, values[-1][1] * scale)

    @staticmethod
    def _read_scale_to_mm(data: bytes) -> float | None:
        """Return the factor from the unit the values are in to mm."""
        for offset, size in VsiImage._find_records(data, _CALIBRATION_UNIT_TAG):
            raw = data[offset + _TLV_HEADER.size : offset + _TLV_HEADER.size + size]
            try:
                unit = raw.decode("utf-16-le")
            except UnicodeDecodeError:
                continue
            if unit == _MICROMETERS:
                return 1 / 1000
            logging.warning(
                "Unknown VSI calibration unit %r, ignoring positions.", unit
            )
            return None
        return None

    @staticmethod
    def _move_onto_slide(images: list["VsiImage"]) -> list["VsiImage"]:
        """Translate all images equally so that none is at a negative position.

        The newer files position images from the corner of the slide by the
        label, which is what DICOM wants. The older ones give raw stage
        coordinates, which are negative, so those are moved onto the slide
        keeping the images in the same place relative to each other.
        """
        origins = [image.origin for image in images if image.origin is not None]
        if not origins:
            return images
        offset = PointMm(
            -min(0.0, min(origin.x for origin in origins)),
            -min(0.0, min(origin.y for origin in origins)),
        )
        if offset.x == 0 and offset.y == 0:
            return images
        return [
            replace(
                image,
                origin=None
                if image.origin is None
                else PointMm(image.origin.x + offset.x, image.origin.y + offset.y),
            )
            for image in images
        ]


class VsiMetadata(WsiDicomizerMetadata):
    def __init__(
        self,
        tiff: TiffFile,
        base_size: Size,
        pyramid_image: VsiImage | None,
        slide_identifier: str | None,
    ):
        """Create metadata for a VSI file.

        Parameters
        ----------
        tiff: TiffFile
            The opened `.vsi` file.
        base_size: Size
            Size in pixels of the base level of the pyramid, used to derive the
            pixel spacing when the file does not state it.
        pyramid_image: VsiImage | None
            The metadata block entry of the converted pyramid, if found.
        slide_identifier: str | None
            The slide name / barcode (tag 2061), if the file states it.
        """
        page = tiff.pages.first
        assert isinstance(page, TiffPage)
        equipment = Equipment(
            manufacturer=page.tags.valueof(MAKE_TAG),
            # Artist is not the scanner but the user that made the scan, so it
            # is neither used as model name nor included.
            model_name=page.tags.valueof(MODEL_TAG),
        )
        pixel_spacing = pyramid_image.pixel_spacing if pyramid_image else None
        origin = pyramid_image.origin if pyramid_image else None
        image = Image(
            pixel_spacing=pixel_spacing or self._get_pixel_spacing(tiff, base_size),
            acquisition_datetime=self._get_datetime(page),
            image_coordinate_system=ImageCoordinateSystem(origin, rotation=0)
            if origin is not None
            else FormatCoordinateDefaults.from_wsi_format(
                WsiFormat.VSI
            ).level_coordinate_system(),
        )
        slide = Slide(identifier=slide_identifier) if slide_identifier else None
        super().__init__(
            equipment=equipment,
            slide=slide,
            pyramid=Pyramid(image=image, optical_paths=[]),
        )

    @classmethod
    def _get_pixel_spacing(cls, tiff: TiffFile, base_size: Size) -> SizeMm | None:
        """Return the pixel spacing of the base level of the pyramid.

        The `.vsi` does not state it directly, so it is derived from one of the
        small images of the scanned area that do carry a physical pixel size in
        the Olympus SIS tag (in meters):

        - The "Sample Mask" image, together with the Exif pixel size of that
          same area at base resolution. This is exact.
        - Otherwise the focus map, whose extent is that of the scanned area, so
          dividing it by the size of the base level gives the pixel spacing.
          Slightly small, as the base level includes the padding of its tile
          grid, by 0.2 % on the slides seen.
        """
        mask = cls._get_sis_page(tiff, lambda name: name == SAMPLE_MASK_NAME)
        if mask is not None and mask.tags.valueof(EXIF_TAG) is not None:
            sis = mask.tags.valueof(OLYMPUS_SIS_TAG)
            exif = mask.tags.valueof(EXIF_TAG)
            return SizeMm(
                sis["pixelsizex"] * 1000 * mask.imagewidth / exif["PixelXDimension"],
                sis["pixelsizey"] * 1000 * mask.imagelength / exif["PixelYDimension"],
            )
        focus_map = cls._get_sis_page(
            tiff, lambda name: name.endswith(FOCUS_MAP_NAME_SUFFIX)
        )
        if focus_map is not None:
            sis = focus_map.tags.valueof(OLYMPUS_SIS_TAG)
            return SizeMm(
                sis["pixelsizex"] * 1000 * focus_map.imagewidth / base_size.width,
                sis["pixelsizey"] * 1000 * focus_map.imagelength / base_size.height,
            )
        logging.warning("Could not determine pixel spacing from %s.", tiff.filename)
        return None

    @staticmethod
    def _get_sis_page(tiff: TiffFile, match: Callable[[str], bool]) -> TiffPage | None:
        """Return the first page with an Olympus SIS tag of a matching name."""
        return next(
            (
                page
                for page in tiff.pages
                if isinstance(page, TiffPage)
                and match((page.tags.valueof(OLYMPUS_SIS_TAG) or {}).get("name", ""))
            ),
            None,
        )

    @staticmethod
    def _get_datetime(page: TiffPage) -> datetime | None:
        value = page.tags.valueof(DATETIME_TAG)
        if value is None:
            return None
        try:
            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            logging.warning("Could not parse datetime %s.", value)
            return None
