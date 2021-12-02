# *wsidicomizer*
*wsidicomizer* is a Python library for converting files wsi files to DICOM. The aims of the project are:
- Provide lossless conversion for files supported by opentile.
- Provide 'as good as possible' conversion for other formats.
- Simplify the encoding of wsi metadata into DICOM.

## Installation
***Download wsidicomizer from git***
```console
$ pip install wsidicomizer
```

***Install OpenSlide***
Instructions for how to install OpenSlide is avaiable on https://openslide.org/download/
For Windows, you need also need add OpenSlide's bin-folder to the environment variable 'OPENSLIDE'

***Install libjpeg-turbo***
Install libjpeg-turbo either as binary from https://libjpeg-turbo.org/ or using your package manager.
For Windows, you also need to add libjpeg-turbo's bin-folder to the environment variable 'TURBOJPEG'

## Important note
Please note that this is an early release and the API is not frozen yet. Function names and functionality is prone to change.

## Requirements
*wsidicomizer* requires python >=3.7 and uses numpy, pydicom, highdicom, imagecodecs, openslide-python, PyTurboJPEG, opentile, and wsidicom.

## Limitations
Files with z-stacks or multiple focal paths are currently not supported. DICOM properties related to slice thickness, focal plane thickness, and imaged volume are saved as 0 and not with proper values.

## Basic cli-usage
***Convert a wsi-file into DICOM using cli-interface***
```console
wsidicomizer -i 'path_to_wsi_file' -o 'path_to_output_folder'
```
### Arguments:
~~~~
-i, --input, path to input wsi file
-o, --output, path to output folder
-t, --tile-size, required depending on input format
-d, --dataset, optional path to json file defining base dataset
-l, --levels, optional levels to include
-w, --workers, number of threads to use
--chunk-size, number of tiles to give each worker at a time
--format, encoding format to use if re-encoding. 'jpeg' or 'jpeg2000'
--quality, quality to use if re-encoding.
--subsampling, subsampling option to use if re-encoding.
~~~~
### Flags
~~~~
--no-label, do not include label(s)
--no-overview, do not include overview(s)
--no-confidential, do not include confidential metadata from image
~~~~
Using the no-confidential-flag properties according to [DICOM Basic Confidentiality Profile](https://dicom.nema.org/medical/dicom/current/output/html/part15.html#table_E.1-1) are not included in the output file. Properties otherwise included are currently:
* Acquisition DateTime
* Device Serial Number

## Basic notebook-usage
***Create module datasets (Optional)***
```python
from wsidicomizer.dataset import create_device_module, create_sample, create_specimen_module, create_brightfield_optical_path_module, create_patient_module, create_study_module
device_module = create_device_module(
    manufacturer='Scanner manufacturer',
    model_name='Scanner model name',
    serial_number='Scanner serial number',
    software_versions=['Scanner software versions']
)
sample = create_sample(
    sample_id='sample id',
    embedding_medium='Paraffin wax',
    fixative='Formalin',
    stainings=['hematoxylin stain', 'water soluble eosin stain']
)
specimen_module = create_specimen_module(
    slide_id='slide id',
    samples=[sample]
)
optical_module = create_brightfield_optical_path_module()
patient_module = create_patient_module()
study_module = create_study_module()

```

***Convert a wsi-file into DICOM using python-interface***
```python
from wsidicomizer import WsiDicomizer
created_files = WsiDicomizer.convert(
    path_to_wsi_file,
    path_to_output_folder,
    [device_module, specimen_module, optical_module, patient_module, study_module],
    tile_size
)
```
tile_size is required for Ndpi- and OpenSlide-files.

***Import a wsi file as a WsiDicom object.***
```python
from wsidicomizer import WsiDicomizer
wsi = WsiDicomizer.import_tiff(path_to_wsi_file)
region = wsi.read_region((1000, 1000), 6, (200, 200))
wsi.close()
```

## Other DICOM python tools
- [pydicom](https://pydicom.github.io/)
- [highdicom](https://github.com/MGHComputationalPathology/highdicom)
- [wsidicom](https://github.com/imi-bigpicture/wsidicom)

## Contributing
We welcome any contributions to help improve this tool for the WSI DICOM community!

We recommend first creating an issue before creating potential contributions to check that the contribution is in line with the goals of the project. To submit your contribution, please issue a pull request on the imi-bigpicture/wsidicomizer repository with your changes for review.

Our aim is to provide constructive and positive code reviews for all submissions. The project relies on gradual typing and roughly follows PEP8. However, we are not dogmatic. Most important is that the code is easy to read and understand.

## TODOs
* Packaging of libjpeg-turbo into an 'ready-to-use' distribution.
* Look into if OpenSlide python will provide a 'ready-to-use' distribution.
* Interface for coding annotations (geometrical, diagnosis using for example structured reporting).

## Acknowledgement
*wsidicomizer*: Copyright 2021 Sectra AB, licensed under Apache 2.0.

This project is part of a project that has received funding from the Innovative Medicines Initiative 2 Joint Undertaking under grant agreement No 945358. This Joint Undertaking receives support from the European Union’s Horizon 2020 research and innovation programme and EFPIA. IMI website: www.imi.europa.eu