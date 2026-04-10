from .....spec.ir._fields import ValueOpIr
from .....spec.ir.lookup_casts import LookupCastSpecIr
from ...schema_dsl.constants import LOOKUP_CAST_NAME_ENUM
from ...schema_dsl.models import LookupCastConfig
from ..errors import ScalimConversionError
from .conversion_lookup import VALUE_CASTS


class ConfigToIRConversionBindingMixin:
    def _get_value_cast_op(self, value_cast: str) -> ValueOpIr:
        if str(value_cast or "").strip() not in VALUE_CASTS:
            msg = "Unknown value_cast: '{}'".format(value_cast)
            raise ScalimConversionError(msg)
        return ValueOpIr(kind="cast", to=str(value_cast))

    def _get_lookup_cast_spec(self, lookup_cast: LookupCastConfig) -> LookupCastSpecIr:
        name = str(lookup_cast.name or "").strip()
        if not name:
            msg = "lookup_cast.name is required"
            raise ScalimConversionError(msg)
        if name not in LOOKUP_CAST_NAME_ENUM:
            msg = "Unknown lookup_cast: '{}'".format(name)
            raise ScalimConversionError(msg)
        return LookupCastSpecIr(name=name, sep=lookup_cast.sep)


__all__ = ()
