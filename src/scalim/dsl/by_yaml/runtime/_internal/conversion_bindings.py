from typing import Callable, Optional

from .....spec.ir.aliases import LookupKeyCast
from .....typedefs import FieldValue
from ...schema_dsl.models import LookupCastConfig
from ..errors import ScalimConversionError
from .conversion_lookup import VALUE_CASTS, LookupCastRegistry


class ConfigToIRConversionBindingMixin:
    _lookup_casts: Optional[LookupCastRegistry] = None

    def _get_value_cast_fn(self, value_cast: str) -> Callable[[FieldValue], FieldValue]:
        fn = VALUE_CASTS.get(value_cast)
        if fn is None:
            msg = "Unknown value_cast: '{}'".format(value_cast)
            raise ScalimConversionError(msg)
        return fn

    def _get_lookup_cast_fn(self, lookup_cast: LookupCastConfig, *, is_multi: bool) -> LookupKeyCast:
        if self._lookup_casts is None:
            msg = "Lookup cast registry is not initialized"
            raise ScalimConversionError(msg)
        return self._lookup_casts.build(lookup_cast, is_multi=is_multi)
