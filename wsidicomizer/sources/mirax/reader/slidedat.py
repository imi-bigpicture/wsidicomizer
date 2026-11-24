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

"""The MIRAX Slidedat.ini: geometry, data-file map, pyramid structure, properties.

`Slidedat` is the sole owner of the parsed Slidedat.ini, exposing both
structural config (data files, level layout) and descriptive metadata.
"""

from configparser import RawConfigParser, SectionProxy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from opentile.geometry import PointF, Size

from wsidicomizer.sources.mirax.reader.errors import MrxsError


@dataclass(frozen=True)
class Channel:
    """A fluorescence channel: display name, the RGB band it's stored in, and its
    display colour. Channels are packed into one RGB tile in BGR order, so
    STORING_CHANNEL_NUMBER 0 is the blue band (index 2), 1 green (1), 2 red (0)."""

    name: str
    band: int
    color: tuple[int, int, int]


class Slidedat:
    """Parsed Slidedat.ini for one slide, with typed accessors."""

    def __init__(self, data_folder: Path):
        """Parse the Slidedat.ini in a slide's data folder.

        Parameters
        ----------
        data_folder: Path
            The slide's data folder, next to the .mrxs file and named after it.
        """
        slidedat = data_folder / "Slidedat.ini"
        if not slidedat.is_file():
            raise MrxsError(f"missing {slidedat}")
        ini = RawConfigParser()
        ini.optionxform = str  # type: ignore[assignment]  # preserve key case
        ini.read_string(slidedat.read_text(encoding="utf-8-sig", errors="replace"))
        self._ini = ini
        self._data_folder = data_folder

    @property
    def imagenumber_x(self) -> int:
        return int(self._ini["GENERAL"]["IMAGENUMBER_X"])

    @property
    def imagenumber_y(self) -> int:
        return int(self._ini["GENERAL"]["IMAGENUMBER_Y"])

    @property
    def divisions(self) -> int:
        """Camera-photo subdivisions per side (tiles per photo edge). Absent in
        v2.3+, where camera images aren't subdivided — each tile is one photo."""
        return int(self._ini["GENERAL"].get("CameraImageDivisionsPerSide", 1))

    @property
    def index_filename(self) -> str:
        return self._ini["HIERARCHICAL"]["INDEXFILE"]

    @property
    def datafiles(self) -> dict[int, Path]:
        """File-number -> Data*.dat path."""
        datafile_section = self._ini["DATAFILE"]
        count = int(datafile_section["FILE_COUNT"])
        return {
            i: self._data_folder / datafile_section[f"FILE_{i}"] for i in range(count)
        }

    @property
    def tile_size(self) -> Size:
        """Source-tile pixel size; uniform across the slide."""
        level0 = self._level0_section()
        return Size(int(level0["DIGITIZER_WIDTH"]), int(level0["DIGITIZER_HEIGHT"]))

    @property
    def overlap(self) -> PointF:
        """Nominal per-photo overlap in level-0 pixels; may be fractional.
        Placement keeps it float and rounds the final tile position, so rounding
        error can't accumulate across photo seams."""
        level0 = self._level0_section()
        return PointF(
            float(level0.get("OVERLAP_X", 0)),
            float(level0.get("OVERLAP_Y", 0)),
        )

    @property
    def fill_bgr(self) -> int:
        """Background fill colour, packed as B<<16 | G<<8 | R."""
        return int(self._level0_section().get("IMAGE_FILL_COLOR_BGR", 16777215))

    @property
    def image_format(self) -> str:
        """Tile encoding: JPEG / JPEG_RGB / BMP24 (8-bit), or PNG / JPEG2000 /
        JPEGXR (16-bit, 48-bit tiles)."""
        return self._level0_section().get("IMAGE_FORMAT", "JPEG")

    @property
    def bit_depth(self) -> int:
        """Bits per channel: 8 or 16 (VIMSLIDE_SLIDE_BITDEPTH; absent => 8)."""
        return int(self._ini["GENERAL"].get("VIMSLIDE_SLIDE_BITDEPTH", 8))

    @property
    def channels(self) -> list[Channel]:
        """Fluorescence channels, or empty for brightfield. Each channel is one
        band of the RGB tile (BGR order, band 2 - STORING_CHANNEL_NUMBER)."""
        general = self._ini["GENERAL"]
        hierarchical = self._ini["HIERARCHICAL"]
        if general.get("SLIDE_TYPE") != "SLIDE_TYPE_FLUORESCENCE":
            return []
        if hierarchical.get("HIER_1_NAME") != "Slide filter level":
            return []
        channels: list[Channel] = []
        for value in range(int(hierarchical["HIER_1_COUNT"])):
            section = self._ini[hierarchical[f"HIER_1_VAL_{value}_SECTION"]]
            storing_number = int(section["STORING_CHANNEL_NUMBER"])
            color = (
                int(section.get("COLOR_R", 255)),
                int(section.get("COLOR_G", 255)),
                int(section.get("COLOR_B", 255)),
            )
            name = section.get("FILTER_NAME", "?")
            channels.append(Channel(name, 2 - storing_number, color))
        return channels

    @property
    def channels_single_leaf(self) -> bool:
        """True when every channel's pixels live in one shared data leaf (all
        filter levels name the same DATA_IN_THIS_FILTER_LEVEL) — i.e. <=3 channels
        BGR-packed into one RGB tile. False means channels span multiple leaves
        (>3 channels, one RGB tile per group of 3), which we don't read."""
        hierarchical = self._ini["HIERARCHICAL"]
        if hierarchical.get("HIER_1_NAME") != "Slide filter level":
            return False
        leaves = set()
        for value in range(int(hierarchical["HIER_1_COUNT"])):
            section = self._ini[hierarchical[f"HIER_1_VAL_{value}_SECTION"]]
            leaves.add(section.get("DATA_IN_THIS_FILTER_LEVEL"))
        return len(leaves) == 1

    @property
    def mpp(self) -> tuple[float, float] | None:
        """Microns per pixel (x, y) at level 0, or None if unspecified."""
        level0 = self._level0_section()
        mpp_x = level0.get("MICROMETER_PER_PIXEL_X")
        mpp_y = level0.get("MICROMETER_PER_PIXEL_Y")
        if not mpp_x or not mpp_y:
            return None
        return float(mpp_x), float(mpp_y)

    @property
    def objective_power(self) -> float | None:
        """Objective magnification, or None if unspecified."""
        power = self._ini["GENERAL"].get("OBJECTIVE_MAGNIFICATION")
        return float(power) if power else None

    @property
    def acquisition_datetime(self) -> datetime | None:
        """Scan time (SLIDE_CREATIONDATETIME), or None if absent/unparseable."""
        raw = self._ini["GENERAL"].get("SLIDE_CREATIONDATETIME")  # 29/12/2009 12:43:52
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
        except ValueError:
            return None

    @property
    def software_versions(self) -> list[str] | None:
        """Scanner software version, or None. SCANNER_SOFTWARE_VERSION lives in the
        scan-data layer section, whose name varies, so scan every section."""
        for section in self._ini.sections():
            version = self._ini[section].get("SCANNER_SOFTWARE_VERSION")
            if version:
                # INI storage has comma, but SliceViewer display them as dot
                return [version.replace(",", ".")]
        return None

    @property
    def scanner_hardware_version(self) -> str | None:
        """Scanner model (SCANNER_HARDWARE_VERSION), or None; absent on older
        Pannoramic slides."""
        for section in self._ini.sections():
            version = self._ini[section].get("SCANNER_HARDWARE_VERSION")
            if version:
                return version
        return None


    @property
    def scanner_hardware_id(self) -> str | None:
        """Scanner serial number (SCANNER_HARDWARE_ID), or None; absent on older
        Pannoramic slides."""
        return self._general_value("SCANNER_HARDWARE_ID")

    @property
    def slide_name(self) -> str | None:
        """Slide name (SLIDE_NAME), or None."""
        return self._general_value("SLIDE_NAME")

    @property
    def slide_id(self) -> str | None:
        """Slide identifier (SLIDE_ID), or None."""
        return self._general_value("SLIDE_ID")

    def nonhierarchical_entries(self) -> list[tuple[str, str]]:
        """Flat (group_name, value_name) list, in the order the index stores it."""
        hierarchical = self._ini["HIERARCHICAL"]
        entries: list[tuple[str, str]] = []
        for group_index in range(int(hierarchical["NONHIER_COUNT"])):
            group_name = hierarchical[f"NONHIER_{group_index}_NAME"]
            value_count = int(hierarchical[f"NONHIER_{group_index}_COUNT"])
            for value_index in range(value_count):
                value_name = hierarchical[f"NONHIER_{group_index}_VAL_{value_index}"]
                entries.append((group_name, value_name))
        return entries

    def _level0_section(self) -> SectionProxy:
        return self._ini[self._ini["HIERARCHICAL"]["HIER_0_VAL_0_SECTION"]]

    def _general_value(self, key: str) -> str | None:
        """A [GENERAL] value, or None if absent or empty."""
        return self._ini["GENERAL"].get(key) or None
