# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
from collections import deque
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, Union, cast

from .....spec.ir.binding import LoaderIr
from .....spec.ir.fields import DerivedFieldIr, FieldIr
from .....spec.ir.relations import LookupStepIr  # noqa: TC001
from .....spec.ir.sources import KeyIr, MainSourceIr, OrderByKeyIr, SourceIr
from .....typedefs import SourceSpecIrCacheMode
from ...config_parsing.call_by import CallByParseError, CallByValue, parse_call_by
from ...config_parsing.security import is_constant_compute_expression
from ...schema_dsl.models import DemandConfig, DerivedFieldConfig, MainSourceConfig, SourceConfig, SourceFieldConfig
from ..errors import ConversionError
from .conversion_lookup import CALL_BY_CTX_KEY, validate_source_id

if TYPE_CHECKING:
    from .....spec.ir.aliases import LoaderResultMapCallable, MainSourceRowIterableCallable


class ConfigToIRConversionSourceMixin:
    def _resolve_required_field_ids(self, config: DemandConfig) -> Optional[Set[str]]:
        if config.output is None or not config.output.fields:
            return None

        output_fields = [str(item) for item in config.output.fields]
        required: Set[str] = set(output_fields)
        queue: "deque[str]" = deque(field_id for field_id in output_fields if field_id in config.derived_fields)

        while queue:
            field_id = queue.popleft()
            derived = config.derived_fields.get(field_id)
            if derived is None:
                continue
            for dep in derived.depends_on:
                if dep in required:
                    continue
                required.add(dep)
                if dep in config.derived_fields:
                    queue.append(dep)

        for item in config.main_source.order_by:
            raw = str(item).strip()
            if not raw:
                continue
            field_id = raw[1:] if raw.startswith("-") else raw
            if field_id:
                required.add(field_id)

        return required

    def _convert_main_source(self, config: MainSourceConfig) -> MainSourceIr:
        if not config.source_id:
            msg = "Main source 'source_id' is required"
            raise ConversionError(msg)
        validate_source_id(config.source_id, "Main source")
        if not config.loader:
            msg = "Main source 'loader' is required"
            raise ConversionError(msg)

        loader_fn = cast("MainSourceRowIterableCallable", self._resolver.resolve(config.loader))
        order_by = self._convert_main_source_order_by(config.order_by)

        return MainSourceIr(
            source_id=config.source_id,
            loader=loader_fn,
            params=dict(config.params or {}),
            order_by=order_by,
        )

    def _convert_main_source_order_by(self, order_by: Tuple[str, ...]) -> Tuple[OrderByKeyIr, ...]:
        if not order_by:
            return ()
        converted: List[OrderByKeyIr] = []
        for item in order_by:
            raw = str(item).strip()
            if not raw or raw == "-":
                msg = "Main source order_by contains invalid field"
                raise ConversionError(msg)
            direction = "desc" if raw.startswith("-") else "asc"
            field_id = raw[1:] if raw.startswith("-") else raw
            converted.append(OrderByKeyIr(field_key=field_id, direction=direction))
        return tuple(converted)

    def _convert_source(self, source_config: SourceConfig) -> SourceIr:
        validate_source_id(source_config.source_id, "Source")
        loader_fn = cast("LoaderResultMapCallable", self._resolver.resolve(source_config.loader))

        lookup_cast_fn = None
        if source_config.lookup_cast is not None:
            is_multi = isinstance(source_config.key, tuple)
            lookup_cast_fn = self._get_lookup_cast_fn(source_config.lookup_cast, is_multi=is_multi)

        key_ir = KeyIr(key=source_config.key, cast=lookup_cast_fn)

        bind_ir = None
        if source_config.bind is not None:
            bind_ir = self._create_binding(source_config.bind, source_config.params, source_config.key)

        loader_ir = self._make_loader_ir(callable_ref=loader_fn)

        cache_mode = SourceSpecIrCacheMode.NONE
        if source_config.cache_mode == "preload_forever":
            cache_mode = SourceSpecIrCacheMode.PRELOAD_FOREVER

        fk_fields: FrozenSet[str] = frozenset()

        return SourceIr(
            source_id=source_config.source_id,
            key=key_ir,
            loader_spec=loader_ir,
            fk_fields=fk_fields,
            cache_mode=cache_mode,
            lookup_chunk_size=source_config.lookup_chunk_size,
            bindings={},
            bind=bind_ir,
        )

    def _make_loader_ir(self, callable_ref: Callable[..., Any]) -> LoaderIr:
        return LoaderIr(callable=callable_ref, bindings={})

    def _convert_source_field(self, field_config: SourceFieldConfig, config: DemandConfig) -> FieldIr:
        from_source_id = field_config.source
        data_key = field_config.field or field_config.field_id
        if not from_source_id:
            msg = "Field '{}' missing source".format(field_config.field_id)
            raise ConversionError(msg)
        if not data_key:
            msg = "Field '{}' missing field".format(field_config.field_id)
            raise ConversionError(msg)

        source_ir: Optional[Union[SourceIr, MainSourceIr]] = None
        if self._main_source_ir and from_source_id == self._main_source_ir.source_id:
            source_ir = self._main_source_ir
        else:
            source_ir = self._sources_ir.get(from_source_id)
        if source_ir is None:
            msg = "Field '{}' references unknown source '{}'".format(field_config.field_id, from_source_id)
            raise ConversionError(msg)

        transform: Optional[Callable[[Any], Any]] = None
        if field_config.value_cast:
            transform = self._get_value_cast_fn(field_config.value_cast)

        lookup_steps: Optional[Tuple[LookupStepIr, ...]] = None
        if isinstance(source_ir, SourceIr):
            lookup_steps = self._resolve_lookup_steps(field_config, config, source_ir)

        return FieldIr(
            field_id=field_config.field_id,
            name=field_config.name or field_config.field_id,
            source=source_ir,
            data_key=data_key,
            is_primary=False,
            transform=transform,
            relation=None,
            lookup_steps=lookup_steps,
        )

    def _convert_derived_field(self, derived_config: DerivedFieldConfig) -> DerivedFieldIr:
        call_ctx_key = None
        is_constant_compute = False
        if derived_config.compute:
            calculator = self._compute_engine.compile(derived_config.compute, derived_config.depends_on)
            if not derived_config.depends_on and is_constant_compute_expression(derived_config.compute):
                is_constant_compute = True
        elif derived_config.call_by:
            calculator = self._compile_call_by(field_id=derived_config.field_id, call_by=derived_config.call_by)
            call_ctx_key = CALL_BY_CTX_KEY
        else:
            msg = "Derived field '{}' must declare 'compute' or 'call_by'".format(derived_config.field_id)
            raise ConversionError(msg)

        return DerivedFieldIr(
            field_id=derived_config.field_id,
            name=derived_config.name,
            dependencies=derived_config.depends_on,
            calculator=calculator,
            call_ctx_key=call_ctx_key,
            is_constant_compute=is_constant_compute,
        )

    def _compile_call_by(self, *, field_id: str, call_by: str) -> Callable[..., Any]:
        try:
            parsed = parse_call_by(call_by)
        except CallByParseError as exc:
            msg = "Derived field '{}' has invalid call_by: {}".format(field_id, exc)
            raise ConversionError(msg) from exc

        try:
            fn = self._resolver.resolve(parsed.reference)
        except Exception as exc:
            msg = "Derived field '{}' failed to resolve call_by reference '{}': {}".format(field_id, parsed.reference, exc)
            raise ConversionError(msg) from exc

        def _eval_value(value: CallByValue, field_values: Dict[str, Any]) -> Any:
            if value.kind == "literal":
                return value.value
            if value.kind == "field":
                return field_values.get(value.value)
            ctx = field_values.get(CALL_BY_CTX_KEY)
            if ctx is None:
                msg = "call_by requires context, but '{}' is missing".format(CALL_BY_CTX_KEY)
                raise ValueError(msg)
            if value.kind == "ctx":
                return ctx
            if value.kind == "ctx_attr":
                return getattr(ctx, value.value)
            msg = "Unknown call_by value kind: {}".format(value.kind)  # pragma: no cover
            raise ValueError(msg)  # pragma: no cover

        def calculator(**field_values: Any) -> Any:
            args = [_eval_value(v, field_values) for v in parsed.args]
            kwargs = {k: _eval_value(v, field_values) for k, v in parsed.kwargs}
            return fn(*args, **kwargs)

        return calculator
