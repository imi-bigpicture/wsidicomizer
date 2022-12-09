#    Copyright 2022 SECTRA AB
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

import os
from pathlib import Path
from typing import Any, Dict
import requests
from hashlib import md5
import zipfile

FILES: Dict[str, Dict[str, Any]] = {
    'slides/svs/CMU-1/CMU-1.svs': {
        'url': 'https://data.cytomine.coop/open/openslide/aperio-svs/CMU-1.svs',  # NOQA
        'md5': {'CMU-1.svs': '751b0b86a3c5ff4dfc8567cf24daaa85'}
    },
    'slides/ndpi/CMU-1/CMU-1.ndpi': {
        'url': 'https://data.cytomine.coop/open/openslide/hamamatsu-ndpi/CMU-1.ndpi',  # NOQA
        'md5': {'CMU-1.ndpi': 'fb89dea54f85fb112e418a3cf4c7888a'}
    },
    'slides/mirax/CMU-1/CMU-1.zip': {
        'url': 'https://data.cytomine.coop/open/openslide/mirax-mrxs/CMU-1.zip',  # NOQA
        'md5': {
            'CMU-1/Data0000.dat': 'c3bed9f24edbc4833cb55d7feb7b82a4',
            'CMU-1/Data0001.dat': '275cc207942c333ffc49591a4c6999b7',
            'CMU-1/Data0002.dat': '66a876b3de3ee8fff512fa50bfba8ea0',
            'CMU-1/Data0003.dat': '8ab6845eb71e258fdfc17c19ec3f1db1',
            'CMU-1/Data0004.dat': 'bdf4f6a77b67f35e7d12a91cd9f7d1fc',
            'CMU-1/Data0005.dat': '080f3301232cb95aea7de3ee9105f008',
            'CMU-1/Data0006.dat': '1ada3425f1fa7f2c07a5b33ad09a07c8',
            'CMU-1/Data0007.dat': '3fb30222b26a2f312def828cfe5481fe',
            'CMU-1/Data0008.dat': 'c1509ff7103e3597dccbe387ce21a01f',
            'CMU-1/Data0009.dat': 'e8a8ace5d61b9c379086c2603697f0ce',
            'CMU-1/Data0010.dat': '78761caf4b66e816687188b210d92cc3',
            'CMU-1/Data0011.dat': 'e08751d86e8d33fe552bb4e77c2a980c',
            'CMU-1/Data0012.dat': '6ffc94a4a2579e8ef4985a5d2db72e01',
            'CMU-1/Data0013.dat': 'be8189d90e6f8967deaad09afbf59f57',
            'CMU-1/Data0014.dat': 'a37a62aa2c31bd3d52561031fedcc32c',
            'CMU-1/Data0015.dat': 'e8fca3a59a7f01b51ad5706f811d76b2',
            'CMU-1/Data0016.dat': '17a80b7ac5d8fc97cb9c1c06e9fe72b8',
            'CMU-1/Data0017.dat': '5cd48c4ee038f15941955010d36cafe7',
            'CMU-1/Data0018.dat': 'ff577e91c74d4cb4f9377648dfa78f3e',
            'CMU-1/Data0019.dat': '74a2a435d776b7bec867196475ad8161',
            'CMU-1/Data0020.dat': '14d5a596f0c9bca1aa3b1de8c3557782',
            'CMU-1/Data0021.dat': 'a0a6bd905b00e5957d23560b65762e49',
            'CMU-1/Data0022.dat': 'e309e7afc7c4992e31bef7cd4b21ec05',
            'CMU-1/Index.dat': '117b946c5e805c37c391491f3078ed22',
            'CMU-1/Slidedat.ini': '6727b40350ac487cdf34b81d40a3e193',
            'CMU-1.mrxs': 'bdd39452b8cca4778e862a1298e4aee4'
        },
        'zip': True
    }
}

DEFAULT_DIR = 'testdata'
DOWNLOAD_CHUNK_SIZE = 8192


def download_file(url: str, filename: Path):
    with requests.get(url, stream=True) as request:
        request.raise_for_status()
        with open(filename, 'wb') as file:
            for chunk in request.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                file.write(chunk)


def main():
    print('Downloading and/or checking testdata from openslide.')
    test_data_path = os.environ.get('WSIDICOMIZER_TESTDIR')
    if test_data_path is None:
        test_data_dir = Path(DEFAULT_DIR)
        print(
            'Env "WSIDICOMIZER_TESTDIR" not set, '
            'downloading to default folder '
            f'{test_data_dir}.'
        )
    else:
        test_data_dir = Path(test_data_path)
        print(f'Downloading to {test_data_dir}')

    os.makedirs(test_data_dir, exist_ok=True)
    for file, file_settings in FILES.items():
        file_path = test_data_dir.joinpath(file)
        if file_path.parent.exists():
            print(f'Folder for {file} found, skipping download')
        else:
            url = file_settings['url']
            print(f'Folder for {file} not found, downloading from {url}')
            os.makedirs(file_path.parent, exist_ok=True)
            download_file(url, file_path)

            if file_settings.get('zip'):
                with zipfile.ZipFile(file_path, 'r') as zip:
                    zip.extractall(file_path.parent)
                os.remove(file_path)

        for relative_path, hash in file_settings['md5'].items():
            saved_file_path = file_path.parent.joinpath(relative_path)
            if not saved_file_path.exists():
                raise ValueError(
                    f'Did not find {saved_file_path}. Try removing the '
                    'parent folder and try again.'
                )
            with open(saved_file_path, 'rb') as saved_file_io:
                data = saved_file_io.read()
                if not hash == md5(data).hexdigest():
                    raise ValueError(
                        f'Checksum faild for {saved_file_path}. Try removing '
                        'the parent folder and try again.'
                    )
                else:
                    print(f'{saved_file_path} checksum OK')


if __name__ == '__main__':
    main()
