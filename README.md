# *wsidicomizer*
*wsidicomizer* is a Python library for converting files wsi files to dicom using opentile.

## Important note
Please note that this is an early release and the API is not frozen yet. Function names and functionality is prone to change.

## Requirements
*wsidicomizer* uses PyTurboJPEG, opentile, and wsidicom.

## Limitations
Files with z-stacks are currently not supported.

## Basic usage
***Create a tiler for a ndpi-file using tile size (1024, 1024) pixels.***
```python
from opentile import OpenTile
tile_size = (1024, 1024)
turbo_path = 'C:/libjpeg-turbo64/bin/turbojpeg.dll'
ndpi_tiler = OpenTile.open(path_to_ndpi_file, tile_size, turbo_path)
```

***Import the ndpi-file into a WsiDicom object.***
```python
from wsidicomizer import WsiDicomizer
wsi = WsiDicomizer.import_tiler(ndpi_tiler)
region = wsi.read_region((1000, 1000), 6, (200, 200))
wsi.close()
```

***Convert the Ndpi-file into Dicom files. Use a (test) base dataset that will be common for all created Dicom instances.***
```python
from wsidicomizer import WsiDicomizer
base_dataset = WsiDataset.create_test_base_dataset()
WsiDicomizer.convert(path_to_export_folder, ndpi_tiler, base_dataset)
```
