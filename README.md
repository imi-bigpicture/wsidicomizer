# *wsidicomizer*
*wsidicomizer* is a Python library for converting files wsi files to dicom using opentile or openslide.

## Important note
Please note that this is an early release and the API is not frozen yet. Function names and functionality is prone to change.

## Requirements
*wsidicomizer* requires python >=3.7 and uses numpy, pydicom, highdicom, imagecodecs, openslide-python, PyTurboJPEG, opentile, and wsidicom.

## Limitations
Files with z-stacks or multiple focal paths are currently not supported.

## Basic usage
***Convert a wsi-file into DICOM using cli-interface***
```bash
wsidicomizer/cli.py -i 'path_to_wsi_file' -o 'path_to_output_folder'
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

***Convert a wsi-file into DCIOM using python-interface***
```python
from wsidicomizer import WsiDicomizer
WsiDicomizer.convert(
    path_to_wsi_filee,
    path_to_export_folder,
    tile_size
)
```

***Import a wsi file as a WsiDicom object.***
```python
from wsidicomizer import WsiDicomizer
wsi = WsiDicomizer.import_tiff(path_to_wsi_file)
region = wsi.read_region((1000, 1000), 6, (200, 200))
wsi.close()
```