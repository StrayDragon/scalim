from typing import TYPE_CHECKING, Callable, Optional

from .....spec.ir.aliases import LoaderParamsBuilder, LookupKeyCast, NormalizedLookupKeySpec
from .....spec.ir.binding import BindingIr, build_stable_lookup_key_list
from .....typedefs import FieldValue, LoaderCallParams, StaticParams
from ...schema_dsl.constants import DEFAULT_BIND_AS, DEFAULT_BIND_CACHE_MODE
from ...schema_dsl.models import BindConfig, LookupCastConfig
from ..errors import ConversionError
from .conversion_lookup import VALUE_CASTS, LookupCastRegistry

if TYPE_CHECKING:
    from .....spec.ir.binding import LoaderCallContextIr


class ConfigToIRConversionBindingMixin:
    _lookup_casts: Optional[LookupCastRegistry] = None

    def _create_binding(
        self,
        bind_config: BindConfig,
        static_params: Optional[StaticParams],
        key_field: NormalizedLookupKeySpec,
    ) -> BindingIr:
        if bind_config.use_rows is not None:
            mode = "rows"
            as_mode = DEFAULT_BIND_AS
            cache_mode = bind_config.use_rows.cache_mode or DEFAULT_BIND_CACHE_MODE
            param_name = bind_config.use_rows.param
        elif bind_config.use_keys is not None:
            mode = "keys"
            as_mode = bind_config.use_keys.as_
            cache_mode = "none"
            param_name = bind_config.use_keys.param
        else:
            msg = "BindConfig requires use_rows or use_keys"
            raise ConversionError(msg)
        params_builder = self._create_params_builder(bind_config, static_params)
        return BindingIr(
            key_field=key_field,
            params_builder=params_builder,
            mode=mode,
            as_=as_mode,
            cache_mode=cache_mode or "none",
            param_name=param_name,
        )

    def _create_params_builder(
        self,
        bind_config: BindConfig,
        static_params: Optional[StaticParams] = None,
    ) -> LoaderParamsBuilder:
        base_params: StaticParams = dict(static_params) if static_params else {}
        if bind_config.use_rows is not None:
            param_name = bind_config.use_rows.param
            mode = "rows"
            as_mode = DEFAULT_BIND_AS
        elif bind_config.use_keys is not None:
            param_name = bind_config.use_keys.param
            mode = "keys"
            as_mode = bind_config.use_keys.as_
        else:
            msg = "BindConfig requires use_rows or use_keys"
            raise ConversionError(msg)

        def _builder(ctx: "LoaderCallContextIr") -> LoaderCallParams:
            params: StaticParams = dict(base_params)
            if mode == "rows":
                params[param_name] = ctx.batch_rows or []
                return (), params

            keys = ctx.lookup_keys if ctx.lookup_keys is not None else ctx.batch_row_nth
            if as_mode == "list":
                if ctx.lookup_keys_list is not None:
                    params[param_name] = list(ctx.lookup_keys_list)
                elif isinstance(keys, set):
                    params[param_name] = build_stable_lookup_key_list(keys)
                else:
                    params[param_name] = list(keys)
            else:
                params[param_name] = set(keys)
            return (), params

        return _builder

    def _get_value_cast_fn(self, value_cast: str) -> Callable[[FieldValue], FieldValue]:
        fn = VALUE_CASTS.get(value_cast)
        if fn is None:
            msg = "Unknown value_cast: '{}'".format(value_cast)
            raise ConversionError(msg)
        return fn

    def _get_lookup_cast_fn(self, lookup_cast: LookupCastConfig, *, is_multi: bool) -> LookupKeyCast:
        if self._lookup_casts is None:
            msg = "Lookup cast registry is not initialized"
            raise ConversionError(msg)
        return self._lookup_casts.build(lookup_cast, is_multi=is_multi)
