"""Green-field MIRAX (.mrxs) reader.

Exposes a level-local pyramid/tile read API returning Pillow images. Format
reverse-engineered from https://openslide.org/formats/mirax/ and verified
against the openslide test slides; no openslide code was used.
"""

from wsidicomizer.sources.mirax.reader.errors import MrxsError
from wsidicomizer.sources.mirax.reader.mirax_reader import MiraxReader

__all__ = ["MrxsError", "MiraxReader"]
