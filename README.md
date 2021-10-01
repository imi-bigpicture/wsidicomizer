# *wsidicomizer*
*wsidicomizer* is a Python library for converting files wsi files to dicom using opentile or openslide.

## Important note
Please note that this is an early release and the API is not frozen yet. Function names and functionality is prone to change.

## Requirements
*wsidicomizer* requires python >=3.7 and uses numpy, pydicom, highdicom, imagecodecs, openslide-python, PyTurboJPEG, opentile, and wsidicom.

## Limitations
Files with z-stacks or multiple focal paths are currently not supported.

## Basic usage
***Import a ndpi-file into a WsiDicom object.***
```python
from wsidicomizer import WsiDicomizer
tile_size = (1024, 1024)
wsi = WsiDicomizer.import_tiff(
    path_to_ndpi_file,
    tile_size
)
region = wsi.read_region((1000, 1000), 6, (200, 200))
wsi.close()
```

***Convert a Ndpi-file into Dicom files. Use a (test) base dataset that will be common for all created Dicom instances.***
```python
base_dataset = WsiDataset.create_test_base_dataset()
WsiDicomizer.convert(
    path_to_ndpi_file,
    path_to_export_folder,
    base_dataset,
    tile_size
)
```
