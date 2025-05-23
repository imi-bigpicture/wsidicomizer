#    Copyright 2023 SECTRA AB
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

"""Metadata for isyntax file."""

import logging

from wsidicom.metadata import Label

from isyntax import ISyntax
from wsidicomizer.metadata import WsiDicomizerMetadata


class ISyntaxMetadata(WsiDicomizerMetadata):
    def __init__(self, slide: ISyntax):
        try:
            if slide.barcode != "":
                label = Label(barcode=slide.barcode)
            else:
                label = None
        except UnicodeDecodeError:
            logging.warning("Failed to decode barcode", exc_info=True)
            label = None
        super().__init__(label=label)
