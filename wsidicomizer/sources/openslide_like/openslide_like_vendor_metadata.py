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

"""Vendor-specific metadata read from openslide-like property dictionaries.

openslide normalises a handful of properties (``openslide.mpp-x``,
``openslide.objective-power``, ``openslide.vendor`` ...) but leaves each
scanner's own keys untouched in a vendor namespace (``aperio.*``,
``mirax.GENERAL.*``, ``philips.DICOM_*`` ...). The standard ``tiff.*`` tags are
not a cross-vendor baseline: only Hamamatsu (and re-saved generic tiffs)
populate ``tiff.Make``/``Model``, while Aperio and others leave them empty and
carry their identity in the vendor namespace. Parsing is therefore per-vendor,
selected on the normalised vendor tag by :meth:`VendorMetadata.for_vendor`.

Each accessor returns ``None`` when its key is absent or malformed, so a missing
or unparsable key never fails the conversion.
"""

import base64
import binascii
import re
from collections.abc import Mapping
from datetime import datetime


class VendorMetadata:
    """Vendor-specific metadata read from an openslide-like property mapping.

    The base class reads nothing; each vendor subclass overrides the accessors
    for the keys it exposes. Consumed by
    :class:`~wsidicomizer.sources.openslide_like.openslide_like_metadata.OpenSlideLikeMetadata`
    to fill the DICOM model, falling back to a normalised value where an
    accessor returns ``None``.
    """

    _VENDOR: str | None = None
    _TIFF_DATETIME = "%Y:%m:%d %H:%M:%S"

    def __init__(self, properties: Mapping[str, str]):
        self._properties = properties

    @classmethod
    def for_vendor(
        cls, vendor: str | None, properties: Mapping[str, str]
    ) -> "VendorMetadata":
        """Return vendor-specific metadata for the given openslide vendor tag.

        Selects the subclass whose ``_VENDOR`` matches, falling back to the empty
        :class:`VendorMetadata` for unknown or absent vendors.
        """
        tag = (vendor or "").lower()
        for subclass in cls.__subclasses__():
            if tag == subclass._VENDOR:
                return subclass(properties)
        return cls(properties)

    @property
    def manufacturer(self) -> str | None:
        return None

    @property
    def model_name(self) -> str | None:
        return None

    @property
    def device_serial_number(self) -> str | None:
        return None

    @property
    def software_versions(self) -> list[str] | None:
        return None

    @property
    def acquisition_datetime(self) -> datetime | None:
        return None

    @property
    def series_description(self) -> str | None:
        return None

    @property
    def container_identifier(self) -> str | None:
        return None

    @property
    def objective_numerical_aperture(self) -> float | None:
        return None

    @staticmethod
    def parse_datetime(value: str | None, format: str) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.strptime(value, format)
        except ValueError:
            return None

    @staticmethod
    def parse_iso_datetime(value: str | None) -> datetime | None:
        """Parse an ISO 8601 timestamp, tolerating a trailing ``Z``."""
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def parse_dicom_multi(value: str | None) -> list[str] | None:
        """Split a DICOM-style multi-value string ``'"a" "b" "c"'`` into values."""
        if value is None:
            return None
        quoted = re.findall(r'"([^"]*)"', value)
        values = quoted if quoted else value.split()
        return values or None

    @staticmethod
    def parse_float(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def parse_base64(value: str | None) -> str | None:
        """Decode a base64 barcode to text, returning the value as-is if not base64."""
        if value is None:
            return None
        try:
            decoded = base64.b64decode(value, validate=True).decode("ascii")
            return decoded.strip() or None
        except (binascii.Error, ValueError, UnicodeDecodeError):
            return value


class AperioMetadata(VendorMetadata):
    _VENDOR = "aperio"

    @property
    def device_serial_number(self) -> str | None:
        return self._properties.get("aperio.ScanScope ID")

    @property
    def acquisition_datetime(self) -> datetime | None:
        # Aperio splits acquisition into MM/DD/YY + HH:MM:SS (time zone ignored).
        date = self._properties.get("aperio.Date")
        time = self._properties.get("aperio.Time")
        if date is None or time is None:
            return None
        return self.parse_datetime(f"{date} {time}", "%m/%d/%y %H:%M:%S")


class HamamatsuMetadata(VendorMetadata):
    _VENDOR = "hamamatsu"

    @property
    def manufacturer(self) -> str | None:
        return self._properties.get("tiff.Make")

    @property
    def model_name(self) -> str | None:
        return self._properties.get("hamamatsu.Product") or self._properties.get(
            "tiff.Model"
        )

    @property
    def device_serial_number(self) -> str | None:
        return self._properties.get("hamamatsu.NDP.S/N")

    @property
    def software_versions(self) -> list[str] | None:
        software = self._properties.get("tiff.Software")
        return [software] if software else None

    @property
    def acquisition_datetime(self) -> datetime | None:
        return self.parse_datetime(
            self._properties.get("tiff.DateTime"), self._TIFF_DATETIME
        )


class LeicaMetadata(VendorMetadata):
    _VENDOR = "leica"

    @property
    def manufacturer(self) -> str | None:
        return "Leica"

    @property
    def model_name(self) -> str | None:
        model = self._properties.get("leica.device-model")
        return model.split(";", 1)[0] or None if model is not None else None

    @property
    def software_versions(self) -> list[str] | None:
        version = self._properties.get("leica.device-version")
        return version.split(";") if version else None

    @property
    def acquisition_datetime(self) -> datetime | None:
        return self.parse_iso_datetime(self._properties.get("leica.creation-date"))

    @property
    def container_identifier(self) -> str | None:
        return self._properties.get("leica.barcode")

    @property
    def objective_numerical_aperture(self) -> float | None:
        return self.parse_float(self._properties.get("leica.aperture"))


class MiraxMetadata(VendorMetadata):
    _VENDOR = "mirax"

    @property
    def manufacturer(self) -> str | None:
        return "3DHISTECH"

    @property
    def model_name(self) -> str | None:
        # SCANNER_HARDWARE_* are version-gated: absent on older Pannoramic slides.
        return self._general("SCANNER_HARDWARE_VERSION")

    @property
    def device_serial_number(self) -> str | None:
        return self._general("SCANNER_HARDWARE_ID")

    @property
    def software_versions(self) -> list[str] | None:
        software = self._general("SCANNER_SOFTWARE_VERSION")
        return [software] if software else None

    @property
    def acquisition_datetime(self) -> datetime | None:
        return self.parse_datetime(
            self._general("SLIDE_CREATIONDATETIME"), "%d/%m/%Y %H:%M:%S"
        )

    @property
    def series_description(self) -> str | None:
        return self._general("SLIDE_NAME")

    @property
    def container_identifier(self) -> str | None:
        return self._general("SLIDE_ID")

    def _general(self, key: str) -> str | None:
        return self._properties.get(f"mirax.GENERAL.{key}")


class PhilipsMetadata(VendorMetadata):
    _VENDOR = "philips"

    @property
    def manufacturer(self) -> str | None:
        return self._properties.get("philips.DICOM_MANUFACTURER")

    @property
    def device_serial_number(self) -> str | None:
        return self._properties.get("philips.DICOM_DEVICE_SERIAL_NUMBER")

    @property
    def software_versions(self) -> list[str] | None:
        return self.parse_dicom_multi(
            self._properties.get("philips.DICOM_SOFTWARE_VERSIONS")
        )

    @property
    def acquisition_datetime(self) -> datetime | None:
        return self.parse_datetime(
            self._properties.get("philips.DICOM_ACQUISITION_DATETIME"),
            "%Y%m%d%H%M%S.%f",
        )

    @property
    def container_identifier(self) -> str | None:
        return self.parse_base64(self._properties.get("philips.PIM_DP_UFS_BARCODE"))


class TrestleMetadata(VendorMetadata):
    _VENDOR = "trestle"

    @property
    def software_versions(self) -> list[str] | None:
        software = self._properties.get("tiff.Software")
        return [software] if software else None

    @property
    def acquisition_datetime(self) -> datetime | None:
        return self.parse_datetime(
            self._properties.get("tiff.DateTime"), self._TIFF_DATETIME
        )


class VentanaMetadata(VendorMetadata):
    _VENDOR = "ventana"

    # BuildDate is the software build, not the scan, so no acquisition datetime.
    @property
    def device_serial_number(self) -> str | None:
        return self._properties.get("ventana.UnitNumber")

    @property
    def software_versions(self) -> list[str] | None:
        version = self._properties.get("ventana.BuildVersion")
        return [version] if version else None


class GenericTiffMetadata(VendorMetadata):
    _VENDOR = "generic-tiff"

    @property
    def manufacturer(self) -> str | None:
        return self._properties.get("tiff.Make")

    @property
    def model_name(self) -> str | None:
        return self._properties.get("tiff.Model")

    @property
    def software_versions(self) -> list[str] | None:
        software = self._properties.get("tiff.Software")
        return [software] if software else None

    @property
    def acquisition_datetime(self) -> datetime | None:
        return self.parse_datetime(
            self._properties.get("tiff.DateTime"), self._TIFF_DATETIME
        )
