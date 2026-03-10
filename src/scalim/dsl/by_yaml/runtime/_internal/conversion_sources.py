from collections import deque
from typing import TYPE_CHECKING, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, cast

from .....spec.ir.binding import LoaderIr
from .....spec.ir.fields import DerivedFieldIr, FieldIr
from .....spec.ir.sources import KeyIr, MainSourceIr, OrderByKeyIr, SourceIr, SourceRefIr
from .....typedefs import FieldValue, RuntimeValue, SourceSpecIrCacheMode, StaticParams
from ...config_parsing.call_by import CallByParseError, CallByValue, parse_call_by
from ...config_parsing.field_extract import FieldExtractCompileError, compile_field_extract
from ...config_parsing.security import SecureComputeEngine, is_constant_compute_expression
from ...schema_dsl.models import DemandConfig, DerivedFieldConfig, MainSourceConfig, SourceConfig, SourceFieldConfig
from ..errors import ConversionError
from ..references import PythonReferenceResolver
from .conversion_bindings import ConfigToIRConversionBindingMixin
from .conversion_lookup import CALL_BY_CTX_KEY, validate_source_id
from .conversion_relations import ConfigToIRConversionRelationMixin

if TYPE_CHECKING:
    from .....spec.ir.aliases import LoaderResultMapCallable, MainSourceRowIterableCallable
    from .....spec.ir.relations import LookupStepIr


_SUPPORTED_FIELD_VALUE_TYPES = (bool, int, float, str)


def _copy_static_params(params: Optional[Dict[str, RuntimeValue]]) -> StaticParams:
    copied: StaticParams = {}
    if not params:
        return copied
    for key, value in params.items():
        copied[key] = value
    return copied


def _ensure_field_value(value: object, *, field_id: str, producer: str) -> FieldValue:
    if value is None or isinstance(value, _SUPPORTED_FIELD_VALUE_TYPES):
        return value
    msg = "Derived field '{}' {} returned unsupported type '{}'; expected int/float/str/bool/None".format(
        field_id,
        producer,
        type(value).__name__,
    )
    raise TypeError(msg)


def _require_call_by_context(field_values: Dict[str, RuntimeValue]) -> object:
    ctx_value = field_values.get(CALL_BY_CTX_KEY)
    if ctx_value is None:
        msg = "call_by requires context, but '{}' is missing".format(CALL_BY_CTX_KEY)
        raise ValueError(msg)
    return ctx_value


def _resolve_call_by_ctx_attr(ctx: object, attr_name: str) -> RuntimeValue:
    if not hasattr(ctx, attr_name):
        msg = "call_by context missing attribute '{}'".format(attr_name)
        raise AttributeError(msg)
    return getattr(ctx, attr_name)


def _eval_call_by_value(*, field_id: str, value: CallByValue, field_values: Dict[str, RuntimeValue]) -> RuntimeValue:
    kind = value.kind
    if kind == "literal":
        return _ensure_field_value(value.value, field_id=field_id, producer="call_by literal")
    if kind == "field":
        return field_values.get(str(value.value))
    ctx = _require_call_by_context(field_values)
    if kind == "ctx":
        return ctx
    if kind == "ctx_attr":
        return _resolve_call_by_ctx_attr(ctx, str(value.value))
    msg = "Unknown call_by value kind: {}".format(kind)  # pragma: no cover
    raise ValueError(msg)  # pragma: no cover


class ConfigToIRConversionSourceMixin(ConfigToIRConversionBindingMixin, ConfigToIRConversionRelationMixin):
    _resolver: Optional[PythonReferenceResolver] = None
    _compute_engine: Optional[SecureComputeEngine] = None

    def _require_resolver(self) -> PythonReferenceResolver:
        resolver = self._resolver
        if resolver is None:
            msg = "Reference resolver is not initialized"
            raise ConversionError(msg)
        return resolver

    def _require_compute_engine(self) -> SecureComputeEngine:
        compute_engine = self._compute_engine
        if compute_engine is None:
            msg = "Compute engine is not initialized"
            raise ConversionError(msg)
        return compute_engine

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

        loader_fn = cast("MainSourceRowIterableCallable", self._require_resolver().resolve(config.loader))
        order_by = self._convert_main_source_order_by(config.order_by)

        return MainSourceIr(
            source_id=config.source_id,
            loader=loader_fn,
            params=_copy_static_params(config.params),
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
        loader_fn = cast("LoaderResultMapCallable", self._require_resolver().resolve(source_config.loader))

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

    def _make_loader_ir(self, callable_ref: "LoaderResultMapCallable") -> LoaderIr:
        return LoaderIr(callable=callable_ref, bindings={})

    def _resolve_field_source(self, *, from_source_id: str, field_id: str) -> SourceRefIr:
        if self._main_source_ir is not None and from_source_id == self._main_source_ir.source_id:
            return self._main_source_ir

        source_ir = self._require_sources_ir().get(from_source_id)
        if source_ir is None:
            msg = "Field '{}' references unknown source '{}'".format(field_id, from_source_id)
            raise ConversionError(msg)
        return source_ir

    def _convert_source_field(self, field_config: SourceFieldConfig, config: DemandConfig) -> FieldIr:
        from_source_id = field_config.source
        extract_expr = field_config.field_id if field_config.extract is None else str(field_config.extract)
        if not from_source_id:
            msg = "Field '{}' missing source".format(field_config.field_id)
            raise ConversionError(msg)
        if not extract_expr:
            msg = "Field '{}' missing extract".format(field_config.field_id)
            raise ConversionError(msg)

        try:
            extract_segments = compile_field_extract(extract_expr)
        except FieldExtractCompileError as exc:
            msg = "Field '{}' has invalid extract '{}': {}".format(field_config.field_id, extract_expr, str(exc))
            raise ConversionError(msg) from exc

        data_key = field_config.field_id
        if len(extract_segments) == 1 and isinstance(extract_segments[0], str):
            data_key = extract_segments[0]

        source_ir = self._resolve_field_source(from_source_id=from_source_id, field_id=field_config.field_id)

        transform: Optional[Callable[[FieldValue], FieldValue]] = None
        if field_config.value_cast:
            transform = self._get_value_cast_fn(field_config.value_cast)

        lookup_steps: Optional[Tuple["LookupStepIr", ...]] = None
        if isinstance(source_ir, SourceIr):
            lookup_steps = self._resolve_lookup_steps(field_config, config, source_ir)

        return FieldIr(
            field_id=field_config.field_id,
            name=field_config.name or field_config.field_id,
            source=source_ir,
            data_key=data_key,
            extract_expr=extract_expr,
            extract_segments=extract_segments,
            is_primary=False,
            transform=transform,
            relation=None,
            lookup_steps=lookup_steps,
        )

    def _wrap_compute_calculator(
        self,
        *,
        field_id: str,
        raw_calculator: Callable[..., object],
    ) -> Callable[..., FieldValue]:
        def calculator(*args: FieldValue, **field_values: FieldValue) -> FieldValue:
            result = raw_calculator(*args, **field_values)
            return _ensure_field_value(result, field_id=field_id, producer="compute")

        return calculator

    def _convert_derived_field(self, derived_config: DerivedFieldConfig) -> DerivedFieldIr:
        call_ctx_key: Optional[str] = None
        is_constant_compute = False
        calculator: Callable[..., FieldValue]
        if derived_config.compute:
            raw_calculator = cast(
                "Callable[..., object]",
                self._require_compute_engine().compile(derived_config.compute, derived_config.depends_on),
            )
            calculator = self._wrap_compute_calculator(field_id=derived_config.field_id, raw_calculator=raw_calculator)
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

    def _compile_call_by(self, *, field_id: str, call_by: str) -> Callable[..., FieldValue]:
        try:
            parsed = parse_call_by(call_by)
        except CallByParseError as exc:
            msg = "Derived field '{}' has invalid call_by: {}".format(field_id, exc)
            raise ConversionError(msg) from exc

        try:
            fn = cast("Callable[..., object]", self._require_resolver().resolve(parsed.reference))
        except Exception as exc:
            msg = "Derived field '{}' failed to resolve call_by reference '{}': {}".format(field_id, parsed.reference, exc)
            raise ConversionError(msg) from exc

        def calculator(**field_values: RuntimeValue) -> FieldValue:
            args: List[RuntimeValue] = []
            for arg_value in parsed.args:
                args.append(_eval_call_by_value(field_id=field_id, value=arg_value, field_values=field_values))

            kwargs: Dict[str, RuntimeValue] = {}
            for key, kw_value in parsed.kwargs:
                kwargs[key] = _eval_call_by_value(field_id=field_id, value=kw_value, field_values=field_values)

            result = fn(*args, **kwargs)
            return _ensure_field_value(result, field_id=field_id, producer="call_by")

        return calculator
