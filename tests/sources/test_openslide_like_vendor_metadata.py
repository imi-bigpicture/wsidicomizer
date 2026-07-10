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

# Vendor/model/software-version strings below are real, public product
# identifiers. Instance-identifying values (serial numbers, scan dates,
# barcodes, slide ids/names) are placeholders.

from datetime import datetime

from wsidicomizer.sources.openslide_like.openslide_like_metadata import (
    OpenSlideLikeMetadata,
    OpenSlideLikeProperties,
)
from wsidicomizer.sources.openslide_like.openslide_like_vendor_metadata import (
    VendorMetadata,
)


class TestVendorMetadataForVendor:
    def test_philips_reads_dicom_named_keys(self):
        # Arrange
        properties = {
            "philips.DICOM_MANUFACTURER": "PHILIPS",
            "philips.DICOM_DEVICE_SERIAL_NUMBER": "SN-0001",
            "philips.DICOM_SOFTWARE_VERSIONS": '"1.6.5335" "20111209_R44" "4.0.3"',
            "philips.DICOM_ACQUISITION_DATETIME": "20200102030405.000000",
            "philips.PIM_DP_UFS_BARCODE": "MTIzNDU=",  # base64 of "12345"
        }

        # Act
        result = VendorMetadata.for_vendor("philips", properties)

        # Assert
        assert result.manufacturer == "PHILIPS"
        assert result.device_serial_number == "SN-0001"
        assert result.software_versions == ["1.6.5335", "20111209_R44", "4.0.3"]
        assert result.acquisition_datetime == datetime(2020, 1, 2, 3, 4, 5)
        assert result.container_identifier == "12345"  # base64-decoded barcode

    def test_mirax_reads_general_section(self):
        # Arrange
        properties = {
            "mirax.GENERAL.SLIDE_NAME": "slide-1",
            "mirax.GENERAL.SLIDE_ID": "0123456789ABCDEF0123456789ABCDEF",
            "mirax.GENERAL.SLIDE_CREATIONDATETIME": "02/01/2020 03:04:05",
        }

        # Act
        result = VendorMetadata.for_vendor("mirax", properties)

        # Assert
        assert result.manufacturer == "3DHISTECH"
        assert result.series_description == "slide-1"
        assert result.container_identifier == "0123456789ABCDEF0123456789ABCDEF"
        assert result.acquisition_datetime == datetime(2020, 1, 2, 3, 4, 5)

    def test_leica_reads_scn_keys(self):
        # Arrange
        properties = {
            "leica.device-model": "Leica SCN400;Leica SCN",
            "leica.device-version": "1.4.0.9691;1.4.0.9708",
            "leica.creation-date": "2020-01-02T03:04:05.000Z",
            "leica.barcode": "BARCODE-1",
            "leica.aperture": "0.4",
        }

        # Act
        result = VendorMetadata.for_vendor("leica", properties)

        # Assert
        assert result.manufacturer == "Leica"
        assert result.model_name == "Leica SCN400"  # first ;-component
        assert result.container_identifier == "BARCODE-1"
        assert result.objective_numerical_aperture == 0.4
        assert result.acquisition_datetime is not None
        assert result.acquisition_datetime.year == 2020

    def test_aperio_joins_split_date_and_time(self):
        # Arrange
        properties = {
            "aperio.Date": "01/02/20",
            "aperio.Time": "03:04:05",
            "aperio.ScanScope ID": "SCANNER-1",
        }

        # Act
        result = VendorMetadata.for_vendor("aperio", properties)

        # Assert
        assert result.device_serial_number == "SCANNER-1"
        assert result.acquisition_datetime == datetime(2020, 1, 2, 3, 4, 5)

    def test_hamamatsu_falls_back_to_tiff_tags(self):
        # Arrange
        properties = {
            "tiff.Make": "Hamamatsu",
            "tiff.Model": "C10730-02",
            "tiff.Software": "NDP.scan 2.5.86",
            "tiff.DateTime": "2020:01:02 03:04:05",
            "hamamatsu.NDP.S/N": "SN-1",
            "hamamatsu.Product": "C10730-02",
        }

        # Act
        result = VendorMetadata.for_vendor("hamamatsu", properties)

        # Assert
        assert result.manufacturer == "Hamamatsu"
        assert result.model_name == "C10730-02"
        assert result.device_serial_number == "SN-1"
        assert result.software_versions == ["NDP.scan 2.5.86"]
        assert result.acquisition_datetime == datetime(2020, 1, 2, 3, 4, 5)

    def test_trestle_reads_tiff_tags(self):
        # Arrange
        properties = {
            "tiff.Software": "MedScan v3.4.2.1 - Release",
            "tiff.DateTime": "2020:01:02 03:04:05",
        }

        # Act
        result = VendorMetadata.for_vendor("trestle", properties)

        # Assert
        assert result.software_versions == ["MedScan v3.4.2.1 - Release"]
        assert result.acquisition_datetime == datetime(2020, 1, 2, 3, 4, 5)

    def test_ventana_reads_serial_and_build_but_no_datetime(self):
        # Arrange
        properties = {
            "ventana.UnitNumber": "UNIT-1",
            "ventana.BuildVersion": "3.3.1.1",
            "ventana.BuildDate": "January, 02 2020",
        }

        # Act
        result = VendorMetadata.for_vendor("ventana", properties)

        # Assert
        assert result.device_serial_number == "UNIT-1"
        assert result.software_versions == ["3.3.1.1"]
        # BuildDate is the software build, not the scan, so it is not mapped.
        assert result.acquisition_datetime is None

    def test_generic_tiff_reads_tiff_tags(self):
        # Arrange
        properties = {
            "tiff.Make": "SomeScanner",
            "tiff.Model": "Model-1",
            "tiff.Software": "scanner-fw 1.2",
            "tiff.DateTime": "2020:01:02 03:04:05",
        }

        # Act
        result = VendorMetadata.for_vendor("generic-tiff", properties)

        # Assert
        assert result.manufacturer == "SomeScanner"
        assert result.model_name == "Model-1"
        assert result.software_versions == ["scanner-fw 1.2"]
        assert result.acquisition_datetime == datetime(2020, 1, 2, 3, 4, 5)

    def test_non_base64_barcode_is_returned_as_is(self):
        # Arrange
        properties = {"philips.PIM_DP_UFS_BARCODE": "PLAIN-BARCODE-123"}

        # Act
        result = VendorMetadata.for_vendor("philips", properties)

        # Assert
        assert result.container_identifier == "PLAIN-BARCODE-123"

    def test_unknown_vendor_returns_empty(self):
        # Arrange

        # Act
        result = VendorMetadata.for_vendor(None, {"tiff.Make": "SomeScanner"})

        # Assert
        assert result.manufacturer is None
        assert result.acquisition_datetime is None

    def test_malformed_datetime_is_ignored_not_raised(self):
        # Arrange
        properties = {"mirax.GENERAL.SLIDE_CREATIONDATETIME": "not-a-date"}

        # Act
        result = VendorMetadata.for_vendor("mirax", properties)

        # Assert
        assert result.acquisition_datetime is None


class TestOpenSlideLikeMetadataVendorIntegration:
    def test_raw_properties_flow_into_metadata(self):
        # Arrange
        properties = OpenSlideLikeProperties(
            vendor="mirax",
            raw_properties={
                "mirax.GENERAL.SLIDE_NAME": "slide-1",
                "mirax.GENERAL.SLIDE_ID": "0123456789ABCDEF0123456789ABCDEF",
                "mirax.GENERAL.SLIDE_CREATIONDATETIME": "02/01/2020 03:04:05",
            },
        )

        # Act
        result = OpenSlideLikeMetadata(properties, color_profile=None)

        # Assert
        assert result.equipment.manufacturer == "3DHISTECH"
        assert result.series.description == "slide-1"
        assert result.slide.identifier == "0123456789ABCDEF0123456789ABCDEF"
        assert result.pyramid.image.acquisition_datetime == datetime(
            2020, 1, 2, 3, 4, 5
        )
