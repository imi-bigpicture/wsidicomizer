# *wsidicomizer*
*wsidicomizer* is a Python library for converting files wsi files to dicom using opentile or openslide.

## Installation
***Download wsidicomizer from git***
```console
$ python -m pip git+https://github.com/imi-bigpicture/wsidicomizer.git
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
Files with z-stacks or multiple focal paths are currently not supported.

## Basic usage
***Convert a wsi-file into DICOM using cli-interface***
```console
wsidicomizer -i 'path_to_wsi_file' -o 'path_to_output_folder'
```
### Arguments:
-i, --input, path to input wsi file  
-o, --output, path to output folder  
-d, --dataset, optional path to json file defining base dataset  
-t, --tile_size, tile size, required depending on input format  
-l, --levels, optional levels to include  

### Flags
--no_label, do not include label(s)  
--no_overview, do not include overview(s)  

***Create a base dataset***  
```python
from wsidicomizer.dataset import create_device_module, create_simple_sample, create_simple_specimen_module
device_module = create_device_module(
    create_simple_sample='Scanner manufacturer',
    model_name='Scanner model name',
    serial_number='Scanner serial number',
    software_versions=['Scanner software versions']
)
sample = create_simple_sample(
    sample_id='sample id',
    embedding_medium='Paraffin wax',
    fixative='Formalin',
    stainings=['hematoxylin stain', 'water soluble eosin stain']
)
specimen_module = create_simple_specimen_module(
    slide_id='slide id',
    samples=[sample]
)
```

***Convert a wsi-file into DCIOM using python-interface***  
```python
from wsidicomizer import WsiDicomizer
WsiDicomizer.convert(
    path_to_wsi_filee,
    path_to_export_folder,
    [device_module, specimen_module],
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