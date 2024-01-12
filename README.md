# *wsidicomizer*

*wsidicomizer* is a Python library for opening WSIs in proprietary formats and optionally convert them to DICOM. The aims of the project are:

- Provide read support for various proprietary formats.
- Provide lossless conversion for files supported by opentile.
- Provide 'as good as possible' conversion for other formats.
- Simplify the encoding of WSI metadata into DICOM.

## Supported formats

*wsidicomizer* currently supports the following formats:

- Aperio svs (lossless)
- Hamamatsu ndpi (lossless)
- Philips tiff (lossless)
- Zeiss czi (lossy, only base level)
- Optional: Formats supported by Bioformats (lossy)

With the `openslide` extra the following formats are also supported:

- Mirax mrxs (lossy)
- Leica scn (lossy)
- Sakura svslide (lossy)
- Trestle tif (lossy)
- Ventana bif, tif (lossy)
- Hamamatsu vms, vmu (lossy)

The `bioformats` extra by default enables lossy support for the [BSD-licensed Bioformat formats](https://docs.openmicroscopy.org/bio-formats/6.12.0/supported-formats.html).

## Installation

***Install wsidicomizer from pypi***

```console
pip install wsidicomizer
```

See [Openslide support](#openslide-support) and [Bioformats support](#bioformats-support) for how to install optional extras.

***Install libjpeg-turbo***
Install libjpeg-turbo either as binary from <https://libjpeg-turbo.org/> or using your package manager.
For Windows, you also need to add libjpeg-turbo's bin-folder to the environment variable 'Path'

## Important note

Please note that this is an early release and the API is not frozen yet. Function names and functionality is prone to change.

## Requirements

*wsidicomizer* requires python >=3.8 and uses numpy, pydicom, highdicom, imagecodecs, PyTurboJPEG, opentile, and wsidicom.

## Basic cli-usage

***Convert a wsi-file into DICOM using cli-interface***

```console
wsidicomizer -i 'path_to_wsi_file' -o 'path_to_output_folder'
```

### Arguments

~~~~
-i, --input, path to input wsi file
-o, --output, path to output folder
-t, --tile-size, required depending on input format
-m, --metadata, optional path to json file defining metadata
-d, --default-metadata, optional path to json file defining default metadata
-l, --levels, optional levels to include
-w, --workers, number of threads to use
--label, optional label image to use instead of label found in file
--no-label, if not to include label image
--no-overview, if not to include overview image
--no-confidential, if to not include confidential metadata
--chunk-size, number of tiles to give each worker at a time
--format, encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'
--quality, quality to use if re-encoding.
--subsampling, subsampling option to use if re-encoding.
--offset-table, offset table to use, 'bot', 'eot', or 'None'
~~~~

### Flags

~~~~
--no-label, do not include label(s)
--no-overview, do not include overview(s)
--no-confidential, do not include confidential metadata from image
~~~~

Using the no-confidential-flag properties according to [DICOM Basic Confidentiality Profile](https://dicom.nema.org/medical/dicom/current/output/html/part15.html#table_E.1-1) are not included in the output file. Properties otherwise included are currently:

- Acquisition DateTime
- Device Serial Number

## Basic usage

***Create metadata (Optional)***

```python
from wsidicom.conceptcode import (
    AnatomicPathologySpecimenTypesCode,
    ContainerTypeCode,
    SpecimenCollectionProcedureCode,
    SpecimenEmbeddingMediaCode,
    SpecimenFixativesCode,
    SpecimenSamplingProcedureCode,
    SpecimenStainsCode,
)
from wsidicom.metadata import (
    Collection,
    Embedding,
    Equipment,
    Fixation,
    Label,
    Patient,
    Sample,
    Series,
    Slide,
    SlideSample,
    Specimen,
    Staining,
    Study,
)
from wsidicomizer.metadata import WsiDicomizerMetadata

study = Study(identifier="Study identifier")
series = Series(number=1)
patient = Patient(name="FamilyName^GivenName")
label = Label(text="Label text")
equipment = Equipment(
    manufacturer="Scanner manufacturer",
    model_name="Scanner model name",
    device_serial_number="Scanner serial number",
    software_versions=["Scanner software versions"],
)

specimen = Specimen(
    identifier="Specimen",
    extraction_step=Collection(method=SpecimenCollectionProcedureCode("Excision")),
    type=AnatomicPathologySpecimenTypesCode("Gross specimen"),
    container=ContainerTypeCode("Specimen container"),
    steps=[Fixation(fixative=SpecimenFixativesCode("Neutral Buffered Formalin"))],
)

block = Sample(
    identifier="Block",
    sampled_from=[specimen.sample(method=SpecimenSamplingProcedureCode("Dissection"))],
    type=AnatomicPathologySpecimenTypesCode("tissue specimen"),
    container=ContainerTypeCode("Tissue cassette"),
    steps=[Embedding(medium=SpecimenEmbeddingMediaCode("Paraffin wax"))],
)

slide_sample = SlideSample(
    identifier="Slide sample",
    sampled_from=block.sample(method=SpecimenSamplingProcedureCode("Block sectioning")),
)

slide = Slide(
    identifier="Slide",
    stainings=[
        Staining(
            substances=[
                SpecimenStainsCode("hematoxylin stain"),
                SpecimenStainsCode("water soluble eosin stain"),
            ]
        )
    ],
    samples=[slide_sample],
)
metadata = WsiDicomizerMetadata(
    study=study,
    series=series,
    patient=patient,
    equipment=equipment,
    slide=slide,
    label=label,
)
```

***Convert a wsi-file into DICOM using python-interface***

```python
from wsidicomizer import WsiDicomizer
created_files = WsiDicomizer.convert(
    filepath=path_to_wsi_file,
    output_path=path_to_output_folder,
    metadata=metadata,
    tile_size=tile_size
)
```

***Import a wsi file as a WsiDicom object.***

```python
from wsidicomizer import WsiDicomizer
wsi = WsiDicomizer.open(path_to_wsi_file)
region = wsi.read_region((1000, 1000), 6, (200, 200))
wsi.close()
```

## Openslide support

### Installation

Support for reading images using Openslide c library can optionally be enabled by installing *wsidicomizer* with the `openslide` extra:

```console
pip install wsidicomizer[openslide]
```

The OpenSlide extra requires the OpenSlide library to be installed separately. Instructions for how to install OpenSlide is available on <https://openslide.org/download/>
For Windows, you need also need add OpenSlide's bin-folder to the environment variable 'Path'

## Bioformats support

### Installation

Support for reading images using Bioformats java library can optionally be enabled by installing *wsidicomizer* with the `bioformats` extra:

```console
pip install wsidicomizer[bioformats]
```

The `bioformats` extra enables usage of the `bioformats` module and the `bioformats_wsidicomizer`-cli command. The required Bioformats java library (jar-file) is downloaded automatically when the module is imported using [scyjava](https://github.com/scijava/scyjava).

### Using

As the Bioformats library is a java library it needs to run in a java virtual machine (JVM). A JVM is started automatically when the `bioformats` module is imported. The JVM can´t be restarted in the same Python inteprenter, and is therefore left running once started. If you want to shutdown the JVM (without closing the Python inteprenter) you can call the shutdown_jvm()-method:

```python
import scyjava
scyjava.shutdown_jvm()
```

Due to the need to start a JVM, the `bioformats` module is not imported when using the default `WsiDicomzer`-class, instead the `BioformatsDicomizer`-class should be used. Similarly, the Bioformats support is only available in the `bioformats_wsidicomizer`-cli command.

### Bioformats version

The Bioformats java library is available in two versions, one with BSD and one with GPL2 license, and can read several [WSI formats](https://bio-formats.readthedocs.io/en/v6.12.0/supported-formats.html). However, most formats are only available in the GPL2 version. Due to the licensing incompatibility between Apache 2.0 and GPL2, *wsidicomizer* is distributed with a default setting of using the BSD licensed library. The loaded Biformats version can be changed by the user by setting the `BIOFORMATS_VERSION` environmental variable from the default value `bsd:6.12.0`.

## Limitations

Files with z-stacks or multiple focal paths are currently not supported.

## Other DICOM python tools

- [pydicom](https://pydicom.github.io/)
- [highdicom](https://github.com/MGHComputationalPathology/highdicom)
- [wsidicom](https://github.com/imi-bigpicture/wsidicom)

## Contributing

We welcome any contributions to help improve this tool for the WSI DICOM community!

We recommend first creating an issue before creating potential contributions to check that the contribution is in line with the goals of the project. To submit your contribution, please issue a pull request on the imi-bigpicture/wsidicomizer repository with your changes for review.

Our aim is to provide constructive and positive code reviews for all submissions. The project relies on gradual typing and roughly follows PEP8. However, we are not dogmatic. Most important is that the code is easy to read and understand.

## Acknowledgement

*wsidicomizer*: Copyright 2021 Sectra AB, licensed under Apache 2.0.

This project is part of a project that has received funding from the Innovative Medicines Initiative 2 Joint Undertaking under grant agreement No 945358. This Joint Undertaking receives support from the European Union’s Horizon 2020 research and innovation programme and EFPIA. IMI website: <www.imi.europa.eu>
