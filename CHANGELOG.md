# wsidicomizer changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.19.1] - 2025-03-29

### Fixed

- Ensure that thumbnail instances have pixel spacing set.

## [0.19.0] - 2025-03-13

### Changed

- Barcode from iSyntax source used as `BarcodeValue` instead of `LabelText`.

### Fixed

- Non-assigned variable error when no barcode from iSyntax source.
- Pixel spacing parsing for some tiff formats.

## [0.18.0] - 2025-02-18

### Added

- `metadata_post_processor` parameter to  `open()` and `convert()` methods of `WsiDicomizer` to enable additional metadata processing.

### Changed

- Default bioformats version from bsd-6.12.0 to bsd-9.0.1.

### Fixed

- Typo in `__init__()` of `TiffSlideThumbnailImageData`.

## [0.17.0] - 2025-01-30

### Added

- Conversion of thumbnail images.

### Fixed

- Setting of `LossyImageCompression`, `LossyImageCompressionRatio`, and `LossyImageCompressionMethod` when image data requires transcoding.
- Correct `LossyImageCompressionRatio` for `OpenTileImageData`.

## [0.16.0] - 2025-01-29

### Added

- Support for reading isyntax files using pyisyntax.

### Fixed

- Reading correct image size in pyramid series in Bioformats reader.
- Skip non-dyadic pyramid series in Bioformats reader.
- Missing values in `LossyImageCompressionRatio` and `LossyImageCompressionMethod` when converting without re-encoding.
- Pin zarr to <3.0 to fix import exception.

## [0.15.1] - 2025-01-07

### Fixed

- Update of wsidicom dependency to 0.22.0 to fix openslide compatibility.
- Parsing of acquisition datetime for czi-files with zone designation with Python <3.11.

## [0.15.0] - 2024-10-21

### Added

- Support for pydicom 3.0. This requires Pyhton >3.10.

### Removed

- Support for Python 3.9.
- Support for pydicom <3.

### Changed

- Unpinned requirement for numpy to support numpy 2.

## [0.14.2] - 2024-07-01

### Fixed

- Update opentile version to fix missing file handle closing.

## [0.14.1] - 2024-05-07

### Fixed

- Fix stripes with missing image data for czi source.
- Fix possible cache deadlock for czi source.

## [0.14.0] - 2024-04-15

### Added

- Added `add_missing_levels` parameter to cli.

### Fixed

- Missing ´label` parameter in bioformats cli.
- Change to empty `WsiDicomizerMetadata` for bioformat source.

## [0.13.2] - 2024-03-20

### Fixed

- Missing handling of pyramid index when creating WsiInstance using create_instance().

## [0.13.1] - 2024-02-22

### Fixed

- Updated version of `WsiDicom` to 0.20.1 to fix missing to close file handle.

## [0.13.0] - 2024-02-15

### Added

- Support for incorporating ICC profiles from source image if available. This is currently limited to images read by the `OpenTile` and `OpenSlide` source, and only for supported formats (primarily `Aperio svs`).

- If no ICC profile is present in the source file or the provided metadata, an empty profile will be used if the photometric interpretation requires it for DICOM compatibility. This behavior can be disabled with `settings.insert_icc_profile_if_missing = False`

## [0.12.1] - 2024-01-12

### Fixed

- Fixed missing support for Python 3.12.

## [0.12.0] - 2024-01-12

### Changed

- Replaced `Dataset` based metadata by `modules`-parameter to `open()` and `convert()` with metadata models from `WsiDicom`. Use the `metadata`-parameter to define metadata that should override any metadata found in the source file, and the`default_metadata`-parameter to define metadata that should be used if no other metadata is defiend.

### Fixed

- Fixed fetching empty tile regions with tiffslide and openslide.

## [0.11.0] - 2023-12-10

### Changed

- Use `Encoder` from wsidicom for encoding data.
- Moved `include_levels`, `include_label`, and `include_overview` parameters to `save()`.

### Removed

- Support for Python 3.8

## [0.10.2] - 2023-09-01

### Fixed

- Update dependency requirements to allow newer tifffile and imagecodecs.

## [0.10.1] - 2023-07-06

### Fixed

- Incorrect tile size returned by BioformatsImageData _get_tile() on edge tiles.

## [0.10.0] - 2023-06-30

### Changed

- Relaxed python requirement to >= 3.8.
- Bumped wsidicom and opentil versions.
- Restricted pydicom version to < 2.4.
- Openslide library detection now also detects `libopenslide-1.dll`.

### Fixed

- Incorrect detection off blank tiles in the tiffslide source.

## [0.9.3] - 2023-05-17

### Fixed

- Fixed missing label argument in cli.
- Fixed documentation of encoding quality for jpeg 2000 and handling of > 1000 quality settings as lossless in cli.
- Removed duplicate cli code.

## [0.9.2] - 2023-05-11

### Fixed

- Fixed error in readme regarding installation of extras.
- Fixed documentation of encoding quality for jpeg 2000 and handling of > 1000 quality settings as lossless.

## [0.9.1] - 2023-04-16

### Fixed

- Fixed entrypoints for cli.

## [0.9.0] - 2023-04-03

### Added

- Added Bioformats as a optional source.
- Added TiffSlide as a source.

### Changed

- Refactoring to match new Source-pattern in wsidicom.
- Openslide is now an optional dependency that needs to be specifically installed.

## [0.8.0] - 2023-03-21

### Added

- Set image offset from opentile and openslide properties.
- Parameter to change label to given image.

## [0.7.0] - 2023-02-13

### Added

- Parameter to change label to given image.

### Changed

- Refactored to enable re-use of instance creation methods.

## [0.6.0] - 2023-01-25

### Changed

- Added Python 3.11 as supported version.

## [0.5.1] - 2023-01-16

### Fixed

- Fixed changelog date.

## [0.5.0] - 2023-01-16

### Changed

- include_levels now takes a list of level indices instead of pyramid levels.
- Do not overwrite metadata in base dataset with metadata from file.

## [0.4.0] - 2022-12-13

### Added

- Script for downloading test images.
- Parameters for selectiong offset table in convert() and in CLI.

### Fixed

- Handling of OpenSlide images without slide background color.

## [0.3.1] - 2022-09-09

### Fixed

- Support for openslide-python 1.2.

## [0.3.0] - 2022-06-30

### Added

- Block cache for reading czi files to avoid multiple decompressions.

### Changed

- Set background color for czi files based on photometric interpretation.

### Fixed

- Focal plane and image size parsing for czi files.

## [0.2.0] - 2022-05-23

### Added

- Missing attributes for DICOM compatibility.
- \_\_version__ added.

### Changed

- Drop support for Python 3.7.
- Photometric interpreration changed to YBR_FULL_422 for (non-monochrome) jpeg and YBR_ICT or YBR_RCT for jpeg 2000.
- 420 subsampling as default when re-encoding jpeg.

### Fixed

- Correct naming of X/YOffsetInSlideCoordinateSystem attribute.
- Spelling errors.

## [0.1.3] - 2022-02-14

### Changed

- Allow None as pixelspacing.
- Use 512 px as default tile size.

### Fixed

- Encoding of non-8 bit data to jpeg.
- Do not set z to default [0.0].

## [0.1.2] - 2021-12-02

### Changed

- Fix colorspace issue and codec for jpeg2000 encoding.
- Use image bounds if available from Openslide.
- Use background color from Openslide when removing alpha.
- Use Pillow for alpha removal instead of numpy.

## [0.1.1] - 2021-12-02

### Changed

- Updated README.md to new way of opening files as WsiDicom object.

## [0.1.0] - 2021-12-02

### Added

- Initial release of wsidicomizer

[Unreleased]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.19.1..HEAD
[0.19.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.19.0..0.19.1
[0.19.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.18.0..0.19.0
[0.18.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.17.0..0.18.0
[0.17.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.16.0..0.17.0
[0.16.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.15.1..0.16.0
[0.15.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.15.0..0.15.1
[0.15.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.14.2..0.15.0
[0.14.2]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.14.1..0.14.2
[0.14.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.14.0..0.14.1
[0.14.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.13.2..0.14.0
[0.13.2]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.13.1..0.13.2
[0.13.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.13.0..0.13.1
[0.13.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.12.1..0.13.0
[0.12.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.12.0..0.12.1
[0.12.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.11.0..0.12.0
[0.11.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.10.2..0.11.0
[0.10.2]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.10.1..0.10.2
[0.10.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.10.0..0.10.1
[0.10.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.9.3..0.10.0
[0.9.3]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.9.2..0.9.3
[0.9.2]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.9.1..0.9.2
[0.9.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.9.0..0.9.1
[0.9.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.8.0..0.9.0
[0.8.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.7.0..0.8.0
[0.7.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.6.0..0.7.0
[0.6.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.5.1..0.6.0
[0.5.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.5.0..0.5.1
[0.5.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.4.0..0.5.0
[0.4.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.3.1..0.4.0
[0.3.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.3.0..0.3.1
[0.3.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.2.0..0.3.0
[0.2.0]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.1.3..0.2.0
[0.1.3]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.1.2..0.1.3
[0.1.2]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.1.1..0.1.2
[0.1.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.1.0..0.1.1
[0.1.0]: https://github.com/imi-bigpicture/wsidicomizer/tree/v0.1.0
