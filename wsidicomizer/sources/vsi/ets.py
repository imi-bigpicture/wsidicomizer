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

"""Reader for Olympus `.ets` tile containers.

An `.ets` file is the pyramid pixel store of an Olympus VSI slide. It is not
TIFF: a 64-byte `SIS\0` header, a 228-byte `ETS\0` header, the tile bytes
stored contiguously, and a flat index of fixed-size records at the tail. Each
index record gives the tile position, the pyramid level, and the byte range of
one tile, so tiles of a supported codec can be handed to DICOM without
transcoding.

An index record is `[u32 dimension count][u32 per dimension][u64 offset]
[u32 size][u32 unknown]`, so its size depends on the dimension count in the SIS
header: 36 bytes for the four dimensions of a plain slide scan, more when the
file has channels, focal planes or time points. The first two dimensions are
the tile position and the last is the pyramid level.
"""

import struct
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

from wsidicom.geometry import Point, Size

SIS_MAGIC = b"SIS\x00"
ETS_MAGIC = b"ETS\x00"
_IMAGE_SIZE_OFFSET = 0xB8
"""Offset in the ETS header of the dimension count and the sizes following it."""


class EtsFile:
    """A parsed `.ets` tile container."""

    def __init__(self, filepath: Path):
        self._filepath = filepath
        self._file: BinaryIO = open(filepath, "rb")  # noqa: SIM115 closed in close()
        try:
            (
                tile_size,
                image_size,
                dimensions,
                index_offset,
                index_count,
            ) = self._read_headers(self._file)
            self._tile_size = tile_size
            self._image_size = image_size
            self._tiles = self._read_index(
                self._file, dimensions, index_offset, index_count
            )
        except Exception:
            self._file.close()
            raise
        self._levels = [
            Size(
                max(point.x for point in self._tiles[level]) + 1,
                max(point.y for point in self._tiles[level]) + 1,
            )
            for level in sorted(self._tiles)
        ]

    def __enter__(self) -> "EtsFile":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __str__(self) -> str:
        return f"{type(self).__name__} for {self._filepath}"

    @property
    def filepath(self) -> Path:
        return self._filepath

    @property
    def tile_size(self) -> Size:
        """Size of a tile in pixels. All tiles have this size, edges included."""
        return self._tile_size

    @property
    def image_size(self) -> Size | None:
        """Size in pixels of the base level without the padding of its tile grid.

        None for files that do not record it, which the older (VS120 era)
        writer does not.
        """
        return self._image_size

    @property
    def tiled_sizes(self) -> list[Size]:
        """Size in tiles of each pyramid level, largest level first."""
        return self._levels

    def compressed_size(self, level: int) -> int:
        """Return the total size in bytes of the tiles of a level."""
        return sum(size for _, size in self._tiles[level].values())

    def get_tile(self, level: int, tile: Point) -> bytes | None:
        """Return the stored bytes of a tile, or None if it is not in the file."""
        position = self._tiles[level].get(tile)
        if position is None:
            return None
        offset, size = position
        self._file.seek(offset)
        return self._file.read(size)

    def get_any_tile(self, level: int) -> bytes | None:
        """Return the bytes of any stored tile of a level, or None if it is empty.

        A level can be sparse - the scanner omits tiles outside the scanned
        region rather than storing them blank - so the corner tile (0, 0) is not
        guaranteed to be present. Used to sniff the tile format from real data.
        """
        position = next(iter(self._tiles[level].values()), None)
        if position is None:
            return None
        offset, size = position
        self._file.seek(offset)
        return self._file.read(size)

    def close(self) -> None:
        self._file.close()

    @staticmethod
    def is_ets(filepath: Path) -> bool:
        with open(filepath, "rb") as file:
            return file.read(4) == SIS_MAGIC

    @classmethod
    def _read_headers(cls, file: BinaryIO) -> tuple[Size, Size | None, int, int, int]:
        """Parse the SIS and ETS headers.

        Returns the tile size, the unpadded image size if recorded, the
        dimension count, and the position and length of the tile index.
        """
        sis = file.read(64)
        if sis[:4] != SIS_MAGIC:
            raise ValueError(f"Not a SIS header: {sis[:4]!r}.")
        dimensions = struct.unpack_from("<I", sis, 0x0C)[0]
        ets_offset, ets_size = struct.unpack_from("<QI", sis, 0x10)
        index_offset, index_count = struct.unpack_from("<QI", sis, 0x20)
        file.seek(ets_offset)
        ets = file.read(ets_size)
        if ets[:4] != ETS_MAGIC:
            raise ValueError(f"Not an ETS header: {ets[:4]!r}.")
        tile_width, tile_height = struct.unpack_from("<II", ets, 0x1C)
        return (
            Size(tile_width, tile_height),
            cls._read_image_size(ets),
            dimensions,
            index_offset,
            index_count,
        )

    @staticmethod
    def _read_image_size(ets: bytes) -> Size | None:
        """Return the unpadded image size from the tail of the ETS header.

        Stored as `[u32 dimension count][u32 size per dimension]`, the first two
        dimensions being the image size in pixels and any further ones the
        channel and focal plane counts. Left zero by the older writer, in which
        case the size is only known padded to whole tiles.
        """
        count = struct.unpack_from("<I", ets, _IMAGE_SIZE_OFFSET)[0]
        if count < 2 or _IMAGE_SIZE_OFFSET + 4 + 4 * count > len(ets):
            return None
        width, height = struct.unpack_from("<II", ets, _IMAGE_SIZE_OFFSET + 4)
        if width == 0 or height == 0:
            return None
        return Size(width, height)

    @classmethod
    def _read_index(
        cls, file: BinaryIO, dimensions: int, offset: int, count: int
    ) -> dict[int, dict[Point, tuple[int, int]]]:
        """Parse the tile index into level -> position -> (offset, size)."""
        record = struct.Struct("<" + "I" * (1 + dimensions) + "QII")
        file.seek(offset)
        index = file.read(count * record.size)
        if len(index) != count * record.size:
            raise ValueError("Truncated tile index.")
        tiles: dict[int, dict[Point, tuple[int, int]]] = {}
        for values in record.iter_unpack(index):
            x, y, *extra, level = values[1 : 1 + dimensions]
            if any(extra):
                # Channels, focal planes and time points all appear as
                # dimensions between the position and the level.
                raise NotImplementedError(
                    "Only single channel, focal plane and time point files are "
                    f"supported, got dimensions {values[1 : 1 + dimensions]}."
                )
            tiles.setdefault(level, {})[Point(x, y)] = (values[-3], values[-2])
        if sorted(tiles) != list(range(len(tiles))):
            raise ValueError(f"Non-contiguous pyramid levels {sorted(tiles)}.")
        return tiles
