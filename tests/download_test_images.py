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

# Checksum and source-URL literals are unavoidably longer than the line limit.
# ruff: noqa: E501

"""Download the WSI test slides used by the test suite from Hugging Face.

Each slide's original `source` and checksums are recorded in `FILES` for provenance;
the bytes are fetched from the mirror and verified against the recorded sha256. Slides
are keyed by their folder; multi-file formats (e.g. MIRAX) list every member relative to
that folder and each member is fetched individually.
"""

import os
from hashlib import sha256
from pathlib import Path
from typing import Any

import requests

FILES: dict[str, dict[str, Any]] = {
    "svs/CMU-1": {
        "source": "https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1.svs",
        "description": "Brightfield, JPEG",
        "license": "CC0-1.0",
        "sha256": {
            "CMU-1.svs": "00a3d54482cd707abf254fe69dccc8d06b8ff757a1663f1290c23418c480eb30",
        },
    },
    "svs/JP2K-33003-1": {
        "source": "https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/JP2K-33003-1.svs",
        "description": "Aorta tissue, brightfield, JPEG 2000, YCbCr",
        "license": "distributable",
        "sha256": {
            "JP2K-33003-1.svs": "6205ccf75a8fa6c32df7c5c04b7377398971a490fb6b320d50d91f7ba6a0e6fd",
        },
    },
    "svs/CMU-1-JP2K-33005": {
        "source": "https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1-JP2K-33005.svs",
        "description": "Export of CMU-1.svs, brightfield, JPEG 2000, ICT",
        "license": "CC0-1.0",
        "sha256": {
            "CMU-1-JP2K-33005.svs": "9a1923cd9bcb260ba4d99d64f8d6e32550648c332ba48817f920662f3a513420",
        },
    },
    "ndpi/CMU-1": {
        "source": "https://openslide.cs.cmu.edu/download/openslide-testdata/Hamamatsu/CMU-1.ndpi",
        "description": "Small scan with valid JPEG headers, brightfield, circa 2009",
        "license": "CC0-1.0",
        "sha256": {
            "CMU-1.ndpi": "edf4a1ccf395c7000ae93ad3b44c07d97043810e00be0c1d167dd09bbe436e46",
        },
    },
    "mirax/CMU-1": {
        "source": "https://openslide.cs.cmu.edu/download/openslide-testdata/Mirax/CMU-1.zip",
        "description": "Brightfield, JPEG, MIRAX (multi-file), CURRENT_SLIDE_VERSION 1.9",
        "license": "CC0-1.0",
        "sha256": {
            "CMU-1.mrxs": "ecbda43ab9f5ae671dcd3d2957507ed2e45011bd8bcf93eb6dfc0fdd06764152",
            "CMU-1/Data0000.dat": "c1469c6310a96cde2e2245414670f0498e5d74ab233ff59f032cea6c8341885a",
            "CMU-1/Data0001.dat": "f2df242c70cb484e281370d3c307c097685391730bafd1c54bdd29f61db85a1e",
            "CMU-1/Data0002.dat": "7446688c2a4d2eeb622b6a22fb79a3bc5aef72972352d0f63ffdba5c19f4b100",
            "CMU-1/Data0003.dat": "f5d1918c01fa2b3b181666788fd871175877a4a983cbe99e4f904352f5aaa12d",
            "CMU-1/Data0004.dat": "3bb0ed189650fabf6ca10cea91532ac3f382d3965908bd285b7d3d9dc8fa1c9e",
            "CMU-1/Data0005.dat": "10cb6b3144657e13832f02f5427b5c29ab74280dec12b8fd1dc0fd88d1816471",
            "CMU-1/Data0006.dat": "9164c855da12484996cbf858afb39f11c068ebcf377eb13e6e6a4cf86a5fa5b2",
            "CMU-1/Data0007.dat": "d91a4a5aec34bba0b60022ba0afd316964a87f6432867ed3cc1336225057eb59",
            "CMU-1/Data0008.dat": "3bbbdaee985ef1db93c79aa469f339f52970b2322c83e1eb17cff3458a68ce76",
            "CMU-1/Data0009.dat": "4a19b93239c6f222c21bd8fe7a1c9baf4c4a0b5c124a1c7129a4dde925395733",
            "CMU-1/Data0010.dat": "394ce9363b1efae4d2afc4760fc2c5af49dc340b9573624dba495995ad408ce0",
            "CMU-1/Data0011.dat": "4df975599b6f5ed30d4b6e2bc12cb46ab85323e6804e9ac84c141264d6432ea1",
            "CMU-1/Data0012.dat": "d33fc4a6e0edb59d236ee9f45e7624b47337ed1f0fe30780a6c78c0e60ba1487",
            "CMU-1/Data0013.dat": "ef73bf14d109448e764f8c4f8a3d7de86cb0280086c62beae925480d06a571bc",
            "CMU-1/Data0014.dat": "336ef559afbd021d707fadea5999ba2ecd9c021b4a417f457a2a4515abc5ffb2",
            "CMU-1/Data0015.dat": "0e193517abf404d31e51093bbbbe2272a8a54df465aff555e1370f7b938f7d47",
            "CMU-1/Data0016.dat": "a877f1af7f49b69551264117a540c3145b6b873cad00fd1117d4ec18c2b1fb53",
            "CMU-1/Data0017.dat": "04b088a74ea8ce022a0f38e83d7ad2517343dd22c52291a54fce00a0fa2e6421",
            "CMU-1/Data0018.dat": "d52c7f2c890074198eac3481abef0b4932413638f4bb6103229649e6fde56a14",
            "CMU-1/Data0019.dat": "7914f5255b90f0b3582778f3696467609b0149cc75b06bbeb8b63dc444012b25",
            "CMU-1/Data0020.dat": "f718955197f460aed50e6750e8ad49f8329cb94db165e8b5c965fad380dc03a1",
            "CMU-1/Data0021.dat": "ca41322d1919cd7257a12ef08b9ec7800aba4d8d8ab56c93119b14fbc2a12d23",
            "CMU-1/Data0022.dat": "d65db72d79a96bcf382c7e3846670447001b2b24dfafff8725ffa40a00ad317d",
            "CMU-1/Index.dat": "fb2f13828d4579176180989ecb550e0c7cae798b1300991c031112e07f7a8fb8",
            "CMU-1/Slidedat.ini": "c6aa2792a44f84090ff4eec87a766056977693f82c69d3b03304cd15573dc761",
        },
    },
    "isyntax/isyntax1": {
        "source": "https://doi.org/10.5281/zenodo.5037046",
        "description": "iSyntax test slide from the OpenPhi project",
        "license": "MIT",
        "credit": "Bioimage Informatics Group (Ruusuvuori lab)",
        "sha256": {
            "testslide.isyntax": "38e65f4ddd2001f18135a1835807cb5b2303d012a2a63d63cdfa08a9673c849d",
        },
    },
}

DEFAULT_SLIDE_FOLDER = "tests/testdata/slides"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
HASH_CHUNK_SIZE = 1024 * 1024

# Hugging Face dataset mirroring the test slides.
HF_DATASET = "erikgabr/wsi-testdata"
HF_BASE = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main"


def download_file(url: str, filename: Path):
    with requests.get(url, stream=True, timeout=30) as request:
        request.raise_for_status()
        with open(filename, "wb") as file:
            for chunk in request.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                file.write(chunk)


def file_sha256(path: Path) -> str:
    """Return the sha256 of a file, read in chunks so large files are not held in
    memory."""
    hasher = sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(HASH_CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    print("Downloading and/or checking testdata.")
    test_data_folder = os.environ.get("WSIDICOMIZER_TESTDIR")
    if test_data_folder is None:
        slide_path = Path(DEFAULT_SLIDE_FOLDER)
        print(
            'Env "WSIDICOMIZER_TESTDIR" not set, '
            "downloading to default folder "
            f"{slide_path}."
        )
    else:
        slide_path = Path(test_data_folder).joinpath("slides")
        print(f"Downloading to {slide_path}")

    os.makedirs(slide_path, exist_ok=True)
    for folder, file_settings in FILES.items():
        folder_path = slide_path.joinpath(folder)
        for relative_path, hash in file_settings["sha256"].items():
            member_path = folder_path.joinpath(relative_path)
            if not member_path.exists():
                url = f"{HF_BASE}/{folder}/{relative_path}"
                print(f"{relative_path} not found, downloading from {url}")
                os.makedirs(member_path.parent, exist_ok=True)
                download_file(url, member_path)
            if file_sha256(member_path) != hash:
                raise ValueError(
                    f"Checksum failed for {member_path}. Try removing the file "
                    "and trying again."
                )
            print(f"{member_path} checksum OK")


if __name__ == "__main__":
    main()
