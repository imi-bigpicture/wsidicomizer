from pydicom import Dataset
from pydicom.sr.coding import Code


def code_to_dataset(code: Code) -> Dataset:
    dataset = Dataset()
    dataset.CodeValue = code.value
    dataset.CodingSchemeDesignator = code.scheme_designator
    dataset.CodingSchemeVersion = code.scheme_version
    dataset.CodeMeaning = code.meaning
    return dataset
