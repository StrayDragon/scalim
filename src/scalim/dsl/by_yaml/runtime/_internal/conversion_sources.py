from decimal import Decimal
from typing import TYPE_CHECKING, Callable, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, cast

from .....spec.ir import (
    DerivedFieldIr,
    FieldIr,
    KeyIr,
    MainSourceIr,
    OrderByKeyIr,
    SourceIr,
    SourceNormalizeIr,
    SourceNormalizeProjectFieldRuleIr,
    SourceNormalizeStepIr,
    SourceRefIr,
)
from .....spec.ir.aliases import NormalizedLookupKeySpec
from .....spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr
from .....typedefs import FieldValue, LoaderCallKwargs, RuntimeValue, SourceSpecIrCacheMode
from ..._internal.config_parsing.call_by import CallByValue, ScalimCallByParseError, parse_call_by
from ..._internal.config_parsing.field_extract import ScalimFieldExtractCompileError, compile_field_extract
from ..._internal.config_parsing.security import SecureComputeEngine, is_constant_compute_expression
from ...params_template import CompiledParamsTemplate, ScalimParamsTemplateCompileError, compile_params_template
from ...schema_dsl.models import (
    DemandConfig,
    DerivedFieldConfig,
    MainSourceConfig,
    NormalizeConfig,
    NormalizeProjectFieldRuleConfig,
    NormalizeStepConfig,
    SourceConfig,
    SourceFieldConfig,
)
from ..errors import ScalimConversionError
from ..references import PythonReferenceResolver
from .conversion_bindings import ConfigToIRConversionBindingMixin
from .conversion_lookup import CALL_BY_CTX_KEY, validate_source_id
from .conversion_relations import ConfigToIRConversionRelationMixin

if TYPE_CHECKING:
    from .....spec.ir import LookupStepIr
    from .....spec.ir.aliases import LoaderResultMapCallable, MainSourceRowIterableCallable


_SUPPORTED_FIELD_VALUE_TYPES = (bool, int, float, Decimal, str)


def _ensure_field_value(value: object, *, field_id: str, producer: str) -> FieldValue:
    if value is None or isinstance(value, _SUPPORTED_FIELD_VALUE_TYPES):
        return value
    msg = "Derived field '{}' {} returned unsupported type '{}'; expected int/float/Decimal/str/bool/None".format(
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
    if not hasattr(ctx, attr_name):  # pragma: allow-dynattr dsl: call_by ctx attrs
        msg = "call_by context missing attribute '{}'".format(attr_name)
        raise AttributeError(msg)
    return getattr(ctx, attr_name)  # pragma: allow-dynattr dsl: call_by ctx attrs


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
    msg = "Unknown call_by value kind: {}".format(kind)  # pragma: no cover  # pragma: allow-no-cover invariant: exhaustive CallByValue kind
    raise ValueError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: exhaustive CallByValue kind


class ConfigToIRConversionSourceMixin(ConfigToIRConversionBindingMixin, ConfigToIRConversionRelationMixin):
    _resolver: Optional[PythonReferenceResolver] = None
    _compute_engine: Optional[SecureComputeEngine] = None
    _init_vars: Optional[Mapping[str, object]] = None

    def _require_resolver(self) -> PythonReferenceResolver:
        resolver = self._resolver
        if resolver is None:
            msg = "Reference resolver is not initialized"
            raise ScalimConversionError(msg)
        return resolver

    def _require_compute_engine(self) -> SecureComputeEngine:
        compute_engine = self._compute_engine
        if compute_engine is None:
            msg = "Compute engine is not initialized"
            raise ScalimConversionError(msg)
        return compute_engine

    def _resolve_required_field_ids(self, config: DemandConfig) -> Optional[Set[str]]:
        _ = config
        # 由编译后的 `ExecutionPlan` 决定实际目标字段集合;此处不做二次过滤.
        # 注意: `YAML` 的 `outputs`/`where`/`aggregate` 依赖字段注入(`required fields`)在 `outputs` → `OutputCompositionSpec` 阶段完成.
        return None

    def _convert_main_source(self, config: MainSourceConfig) -> MainSourceIr:
        if not config.source_id:
            msg = "Main source 'source_id' is required"
            raise ScalimConversionError(msg)
        validate_source_id(config.source_id, "Main source")
        if not config.loader:
            msg = "Main source 'loader' is required"
            raise ScalimConversionError(msg)

        loader_fn = cast(  # pragma: allow-cast resolver callable typed narrowing
            "MainSourceRowIterableCallable",
            self._require_resolver().resolve(config.loader),
        )
        order_by = self._convert_main_source_order_by(config.order_by)

        init_vars = self._init_vars
        try:
            template = compile_params_template(
                config.params,
                path="main_source.params",
                init_vars=init_vars,
                allow_keys=False,
                allow_rows=False,
            )
        except ScalimParamsTemplateCompileError as exc:
            raise ScalimConversionError(str(exc)) from exc

        params: LoaderCallKwargs = {}
        if not template.is_empty_mapping():
            params = template.render_kwargs(_build_main_source_context(config.source_id), path="main_source.params")

        return MainSourceIr(
            source_id=config.source_id,
            loader=loader_fn,
            params=params,
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
                raise ScalimConversionError(msg)
            direction = "desc" if raw.startswith("-") else "asc"
            field_id = raw[1:] if raw.startswith("-") else raw
            converted.append(OrderByKeyIr(field_key=field_id, direction=direction))
        return tuple(converted)

    def _convert_source(self, source_config: SourceConfig) -> SourceIr:
        validate_source_id(source_config.source_id, "Source")
        loader_fn = cast(  # pragma: allow-cast resolver callable typed narrowing
            "LoaderResultMapCallable",
            self._require_resolver().resolve(source_config.loader),
        )

        lookup_cast_fn = None
        if source_config.lookup_cast is not None:
            is_multi = isinstance(source_config.key, tuple)
            lookup_cast_fn = self._get_lookup_cast_fn(source_config.lookup_cast, is_multi=is_multi)

        key_ir = KeyIr(key=source_config.key, cast=lookup_cast_fn)

        normalize_ir = self._convert_source_normalize(source_config)

        loader_ir = self._make_loader_ir(callable_ref=loader_fn)

        cache_mode = SourceSpecIrCacheMode.NONE
        if source_config.cache_mode == "preload_forever":
            cache_mode = SourceSpecIrCacheMode.PRELOAD_FOREVER

        bind_ir = self._binding_from_params_template(
            source_config,
            cache_mode=cache_mode,
        )

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
            normalize=normalize_ir,
        )

    def _convert_source_normalize(self, source_config: SourceConfig) -> Optional[SourceNormalizeIr]:
        norm = source_config.normalize
        if norm is None:
            return None

        source_id = source_config.source_id
        kind = str(norm.kind or "").strip()
        if kind not in {"index_by_key", "take_first", "project_fields", "map_values"}:
            msg = "sources.{}.normalize.kind must be one of: index_by_key/take_first/project_fields/map_values".format(source_id)
            raise ScalimConversionError(msg)

        call_by_fn = self._convert_source_normalize_call_by_fn(norm, source_id=source_id)

        if kind == "index_by_key":
            return self._convert_source_normalize_index_by_key(source_config, norm=norm, call_by_fn=call_by_fn)
        if kind == "take_first":
            return self._convert_source_normalize_take_first(source_id=source_id, norm=norm, call_by_fn=call_by_fn)
        if kind == "project_fields":
            return self._convert_source_normalize_project_fields(source_id=source_id, norm=norm, call_by_fn=call_by_fn)
        if kind == "map_values":
            return self._convert_source_normalize_map_values(source_id=source_id, norm=norm, call_by_fn=call_by_fn)

        msg = "sources.{}.normalize.kind must be one of: index_by_key/take_first/project_fields/map_values".format(
            source_id
        )  # pragma: no cover  # pragma: allow-no-cover invariant: normalize kind validated above
        raise ScalimConversionError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: normalize kind validated above

    def _convert_source_normalize_call_by_fn(
        self,
        norm: NormalizeConfig,
        *,
        source_id: str,
    ) -> Optional[Callable[..., object]]:
        if norm.call_by is None:
            return None

        call_by_ref = str(norm.call_by or "").strip()
        if not call_by_ref:
            msg = "sources.{}.normalize.call_by must not be empty".format(source_id)
            raise ScalimConversionError(msg)
        try:
            return cast(  # pragma: allow-cast resolver callable typed narrowing
                "Callable[..., object]",
                self._require_resolver().resolve(call_by_ref),
            )
        except Exception as exc:
            msg = "sources.{}.normalize.call_by failed to resolve reference '{}': {}".format(source_id, call_by_ref, str(exc))
            raise ScalimConversionError(msg) from exc

    def _convert_source_normalize_index_by_key(
        self,
        source_config: SourceConfig,
        *,
        norm: NormalizeConfig,
        call_by_fn: Optional[Callable[..., object]],
    ) -> SourceNormalizeIr:
        source_id = source_config.source_id

        key_field = str(norm.key_field or "").strip()
        if not key_field:
            msg = "sources.{}.normalize.key_field is required".format(source_id)
            raise ScalimConversionError(msg)

        on_conflict = str(norm.on_conflict or "error").strip() or "error"
        if on_conflict not in {"error", "first", "last"}:
            msg = "sources.{}.normalize.on_conflict must be one of: error/first/last".format(source_id)
            raise ScalimConversionError(msg)

        if isinstance(source_config.key, tuple):
            msg = "sources.{}.normalize.kind=index_by_key does not support composite key yet".format(source_id)
            raise ScalimConversionError(msg)

        declared_key = str(source_config.key or "").strip()
        if declared_key and declared_key != key_field:
            msg = "sources.{}.normalize.key_field must equal sources.{}.key".format(source_id, source_id)
            raise ScalimConversionError(msg)

        return SourceNormalizeIr(kind="index_by_key", key_field=key_field, on_conflict=on_conflict, call_by=call_by_fn)

    def _convert_source_normalize_take_first(
        self,
        *,
        source_id: str,
        norm: NormalizeConfig,
        call_by_fn: Optional[Callable[..., object]],
    ) -> SourceNormalizeIr:
        on_empty = str(norm.on_empty or "miss").strip() or "miss"
        if on_empty not in {"miss", "null", "error"}:
            msg = "sources.{}.normalize.on_empty must be one of: miss/null/error".format(source_id)
            raise ScalimConversionError(msg)
        return SourceNormalizeIr(kind="take_first", on_empty=on_empty, call_by=call_by_fn)

    def _convert_source_normalize_project_fields(
        self,
        *,
        source_id: str,
        norm: NormalizeConfig,
        call_by_fn: Optional[Callable[..., object]],
    ) -> SourceNormalizeIr:
        on_missing = str(norm.on_missing or "error").strip() or "error"
        if on_missing not in {"error", "null"}:
            msg = "sources.{}.normalize.on_missing must be one of: error/null".format(source_id)
            raise ScalimConversionError(msg)

        fields = self._convert_source_normalize_project_fields_rules(
            norm.fields,
            config_path="sources.{}.normalize.fields".format(source_id),
        )
        return SourceNormalizeIr(kind="project_fields", fields=fields, on_missing=on_missing, call_by=call_by_fn)

    def _convert_source_normalize_map_values(
        self,
        *,
        source_id: str,
        norm: NormalizeConfig,
        call_by_fn: Optional[Callable[..., object]],
    ) -> SourceNormalizeIr:
        steps = norm.steps
        if not steps:
            msg = "sources.{}.normalize.steps must not be empty".format(source_id)
            raise ScalimConversionError(msg)

        converted_steps: List[SourceNormalizeStepIr] = []
        for idx, step in enumerate(steps):
            converted_steps.append(self._convert_source_normalize_step(step, source_id=source_id, idx=idx))

        return SourceNormalizeIr(kind="map_values", steps=tuple(converted_steps), call_by=call_by_fn)

    def _convert_source_normalize_step(
        self,
        step: NormalizeStepConfig,
        *,
        source_id: str,
        idx: int,
    ) -> SourceNormalizeStepIr:
        step_kind = str(step.kind or "").strip()
        step_path = "sources.{}.normalize.steps[{}]".format(source_id, idx)

        if step_kind == "take_first":
            step_on_empty = str(step.on_empty or "miss").strip() or "miss"
            if step_on_empty not in {"miss", "null", "error"}:
                msg = "{}.on_empty must be one of: miss/null/error".format(step_path)
                raise ScalimConversionError(msg)
            return SourceNormalizeStepIr(kind="take_first", on_empty=step_on_empty)

        if step_kind == "project_fields":
            step_on_missing = str(step.on_missing or "error").strip() or "error"
            if step_on_missing not in {"error", "null"}:
                msg = "{}.on_missing must be one of: error/null".format(step_path)
                raise ScalimConversionError(msg)
            step_fields = self._convert_source_normalize_project_fields_rules(
                step.fields,
                config_path="{}.fields".format(step_path),
            )
            return SourceNormalizeStepIr(kind="project_fields", on_missing=step_on_missing, fields=step_fields)

        msg = "{}.kind must be one of: take_first/project_fields".format(step_path)
        raise ScalimConversionError(msg)

    def _convert_source_normalize_project_fields_rules(
        self,
        rules: Mapping[str, object],
        *,
        config_path: str,
    ) -> Tuple[SourceNormalizeProjectFieldRuleIr, ...]:
        if not rules:
            msg = "{} must not be empty".format(config_path)
            raise ScalimConversionError(msg)

        converted: List[SourceNormalizeProjectFieldRuleIr] = []
        for name, rule_obj in rules.items():
            converted.append(self._convert_source_normalize_project_field_rule(name=name, rule_obj=rule_obj, config_path=config_path))
        return tuple(converted)

    def _convert_source_normalize_project_field_rule(
        self,
        *,
        name: str,
        rule_obj: object,
        config_path: str,
    ) -> SourceNormalizeProjectFieldRuleIr:
        if not isinstance(rule_obj, NormalizeProjectFieldRuleConfig):
            msg = "{}.{} must be a normalize project_fields rule".format(config_path, name)
            raise ScalimConversionError(msg)

        from_key = bool(rule_obj.from_key)
        extract_expr = str(rule_obj.extract or "").strip()
        if from_key and extract_expr:
            msg = "{}.{} must not declare both from_key and extract".format(config_path, name)
            raise ScalimConversionError(msg)
        if not from_key and not extract_expr:
            msg = "{}.{} must declare from_key or extract".format(config_path, name)
            raise ScalimConversionError(msg)

        if from_key:
            return SourceNormalizeProjectFieldRuleIr(name=name, from_key=True)

        try:
            segments = compile_field_extract(extract_expr)
        except ScalimFieldExtractCompileError as exc:
            msg = "{}.{} has invalid extract '{}': {}".format(config_path, name, extract_expr, str(exc))
            raise ScalimConversionError(msg) from exc
        return SourceNormalizeProjectFieldRuleIr(
            name=name,
            from_key=False,
            extract_expr=extract_expr,
            extract_segments=segments,
        )

    def _binding_from_params_template(
        self,
        source_config: SourceConfig,
        *,
        cache_mode: SourceSpecIrCacheMode,
    ) -> Optional["BindingIr"]:
        init_vars = self._init_vars
        allow_directives = cache_mode != SourceSpecIrCacheMode.PRELOAD_FOREVER
        try:
            template = compile_params_template(
                source_config.params,
                path="sources.{}.params".format(source_config.source_id),
                init_vars=init_vars,
                allow_keys=allow_directives,
                allow_rows=allow_directives,
            )
        except ScalimParamsTemplateCompileError as exc:
            raise ScalimConversionError(str(exc)) from exc

        if template.is_empty_mapping():
            return None

        return _binding_from_compiled_params_template(
            template,
            key_field=source_config.key,
            path="sources.{}.params".format(source_config.source_id),
        )

    def _make_loader_ir(self, callable_ref: "LoaderResultMapCallable") -> LoaderIr:
        return LoaderIr(callable=callable_ref, bindings={})

    def _resolve_field_source(self, *, from_source_id: str, field_id: str) -> SourceRefIr:
        if self._main_source_ir is not None and from_source_id == self._main_source_ir.source_id:
            return self._main_source_ir

        source_ir = self._require_sources_ir().get(from_source_id)
        if source_ir is None:
            msg = "Field '{}' references unknown source '{}'".format(field_id, from_source_id)
            raise ScalimConversionError(msg)
        return source_ir

    def _convert_source_field(self, field_config: SourceFieldConfig, config: DemandConfig) -> FieldIr:
        from_source_id = field_config.source
        extract_expr = field_config.field_id if field_config.extract is None else str(field_config.extract)
        if not from_source_id:
            msg = "Field '{}' missing source".format(field_config.field_id)
            raise ScalimConversionError(msg)
        if not extract_expr:
            msg = "Field '{}' missing extract".format(field_config.field_id)
            raise ScalimConversionError(msg)

        try:
            extract_segments = compile_field_extract(extract_expr)
        except ScalimFieldExtractCompileError as exc:
            msg = "Field '{}' has invalid extract '{}': {}".format(field_config.field_id, extract_expr, str(exc))
            raise ScalimConversionError(msg) from exc

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
            raw_calculator = cast(  # pragma: allow-cast compute engine compile typed narrowing
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
            raise ScalimConversionError(msg)

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
        except ScalimCallByParseError as exc:
            msg = "Derived field '{}' has invalid call_by: {}".format(field_id, exc)
            raise ScalimConversionError(msg) from exc

        try:
            fn = cast(  # pragma: allow-cast resolver callable typed narrowing
                "Callable[..., object]",
                self._require_resolver().resolve(parsed.reference),
            )
        except Exception as exc:
            msg = "Derived field '{}' failed to resolve call_by reference '{}': {}".format(field_id, parsed.reference, exc)
            raise ScalimConversionError(msg) from exc

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


def _build_main_source_context(source_id: str) -> LoaderCallContextIr:
    return LoaderCallContextIr(source_id=source_id, is_ref_loader=False)


def _binding_from_compiled_params_template(
    template: CompiledParamsTemplate,
    *,
    key_field: NormalizedLookupKeySpec,
    path: str,
) -> BindingIr:
    mode = "keys"
    as_mode = "set"
    cache_mode = "none"

    if template.directive_mode == "rows":
        mode = "rows"
        cache_mode = template.rows_cache_mode
    elif template.directive_mode == "keys":
        as_mode = template.keys_as

    def _builder(
        ctx: LoaderCallContextIr, tmpl: CompiledParamsTemplate = template, p: str = path
    ) -> Tuple[Tuple[RuntimeValue, ...], LoaderCallKwargs]:
        return (), tmpl.render_kwargs(ctx, path=p)

    return BindingIr(
        key_field=key_field,
        params_builder=_builder,
        mode=mode,
        as_=as_mode,
        cache_mode=cache_mode,
        param_name=None,
    )


__all__ = []
