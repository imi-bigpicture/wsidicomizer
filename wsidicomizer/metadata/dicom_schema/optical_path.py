from typing import Any, Dict, Type
from wsidicomizer.metadata.defaults import Defaults
from wsidicomizer.metadata.dicom_schema.base_dicom_schema import DicomSchema
from marshmallow import fields, pre_dump, post_load

from wsidicomizer.metadata.dicom_schema.dicom_fields import (
    CodeDicomField,
    SingleCodeDicomField,
    FlatteningNestedField,
    FloatDicomField,
)
from wsidicom.conceptcode import (
    LightPathFilterCode,
    IlluminationCode,
    ImagePathFilterCode,
    LenseCode,
    IlluminationColorCode,
)

from wsidicomizer.metadata.optical_path import (
    ImagePathFilter,
    LightPathFilter,
    Objectives,
    OpticalFilter,
    OpticalPath,
)


class FilterDicomSchema(DicomSchema):
    @pre_dump
    def pre_dump(self, filter: OpticalFilter, **kwargs):
        return {
            "filters": filter.filters,
            "nominal": filter.nominal,
            "filter_band": [filter.low_pass, filter.high_pass],
        }

    @post_load
    def post_load(self, data: Dict[str, Any], **kwargs):
        filter_band = data.pop("filter_band", None)
        if filter_band is not None:
            data["low_pass"] = filter_band[0]
            data["high_pass"] = filter_band[1]
        return super().post_load(data, **kwargs)


class LightPathFilterDicomSchema(FilterDicomSchema):
    filters = fields.List(
        CodeDicomField(LightPathFilterCode),
        data_key="LightPathFilterTypeStackCodeSequence",
        allow_none=True,
    )
    nominal = fields.Integer(
        data_key="LightPathFilterPassThroughWavelength", allow_none=True
    )
    low_pass = fields.Integer(load_only=True, allow_none=True)
    high_pass = fields.Integer(load_only=True, allow_none=True)
    filter_band = fields.List(
        fields.Integer(),
        data_key="LightPathFilterPassBand",
    )

    @property
    def load_type(self) -> Type[LightPathFilter]:
        return LightPathFilter


class ImagePathFilterDicomSchema(FilterDicomSchema):
    filters = fields.List(
        CodeDicomField(ImagePathFilterCode),
        data_key="ImagePathFilterTypeStackCodeSequence",
        allow_none=True,
    )
    nominal = fields.Integer(
        data_key="ImagePathFilterPassThroughWavelength", allow_none=True
    )
    low_pass = fields.Integer(load_only=True, allow_none=True)
    high_pass = fields.Integer(load_only=True, allow_none=True)
    filter_band = fields.List(
        fields.Integer(),
        data_key="ImagePathFilterPassBand",
    )

    @property
    def load_type(self) -> Type[ImagePathFilter]:
        return ImagePathFilter


class ObjectivesSchema(DicomSchema):
    lenses = fields.List(
        CodeDicomField(LenseCode), data_key="LensesCodeSequence", allow_none=True
    )
    condenser_power = FloatDicomField(data_key="CondenserLensPower", allow_none=True)
    objective_power = FloatDicomField(data_key="ObjectiveLensPower", allow_none=True)
    objective_numerical_aperature = FloatDicomField(
        data_key="ObjectiveLensNumericalAperture", allow_none=True
    )

    @property
    def load_type(self) -> Type[Objectives]:
        return Objectives


class OpticalPathDicomSchema(DicomSchema):
    identifier = fields.String(data_key="OpticalPathIdentifier")
    description = fields.String(data_key="OpticalPathDescription")
    illumination_types = fields.List(
        CodeDicomField(IlluminationCode),
        data_key="IlluminationTypeCodeSequence",
    )
    illumination_wavelength = fields.Integer(
        data_key="IlluminationWaveLength", load_default=None
    )
    illumination_color_code = SingleCodeDicomField(
        IlluminationColorCode,
        data_key="IlluminationColorCodeSequence",
        dump_default=Defaults.illumination,
        load_default=None,
    )

    # icc_profile: Optional[bytes] = None
    light_path_filter = FlatteningNestedField(LightPathFilterDicomSchema())
    image_path_filter = FlatteningNestedField(ImagePathFilterDicomSchema())
    objective = FlatteningNestedField(ObjectivesSchema())

    @property
    def load_type(self) -> Type[OpticalPath]:
        return OpticalPath

    @pre_dump
    def pre_dump(self, optical_path: OpticalPath, **kwargs):
        fields = {
            "identifier": optical_path.identifier,
            "description": optical_path.description,
            "illumination_types": optical_path.illumination_types,
            "light_path_filter": optical_path.light_path_filter,
            "image_path_filter": optical_path.image_path_filter,
            "objective": optical_path.objective,
        }

        if isinstance(optical_path.illumination, float):
            fields["illumination_wavelength"] = optical_path.illumination
        else:
            fields["illumination_color_code"] = optical_path.illumination
        return fields

    @post_load
    def post_load(self, data: Dict[str, Any], **kwargs):
        illumination_wavelength = data.pop("illumination_wavelength", None)
        illumination_color_code = data.pop("illumination_color_code", None)
        if illumination_wavelength is not None:
            data["illumination"] = illumination_wavelength
        elif illumination_color_code is not None:
            data["illumination"] = illumination_color_code
        return super().post_load(data, **kwargs)
