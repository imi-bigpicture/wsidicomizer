# wsidicom changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - ...

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

[Unreleased]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.1.3..HEAD
[0.1.2]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.1.2..0.1.3
[0.1.2]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.1.1..0.1.2
[0.1.1]: https://github.com/imi-bigpicture/wsidicomizer/compare/0.1.0..0.1.1
[0.1.0]: https://github.com/imi-bigpicture/wsidicomizer/tree/v0.1.0
