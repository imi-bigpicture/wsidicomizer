# wsidicomizer changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] -

d

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

[Unreleased]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.10.1..HEAD
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
