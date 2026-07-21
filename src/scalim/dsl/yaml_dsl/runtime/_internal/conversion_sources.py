from typing import TYPE_CHECKING, Any, FrozenSet, List, Mapping, Optional, Set, Tuple

from .....spec.ir import (
    DerivedFieldIr,
    FieldIr,
    KeyIr,
    MainSourceIr,
    OrderByKeyIr,
    SourceIr,
    SourceNormalizeIr,
    SourceRefIr,
)
from .....spec.ir._fields import CallBySpecIr, CallByValueIr, FieldDefaultCaseIr, ValueOpIr, call_by_requires_ctx
from .....spec.ir._source_normalize import SourceNormalizeProjectFieldRuleIr, SourceNormalizeStepIr
from .....spec.ir.aliases import NormalizedLookupKeySpec
from .....spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr
from .....spec.ir.callable_refs import BuiltinCallableIdIr, CallableRefIr, PythonReferenceIr
from .....typedefs import (
    FIELD_VALUE_TYPES,
    FieldValue,
    RuntimeValue,
    SourceSpecIrCacheMode,
    StaticParams,
    format_field_value_expected_types,
)
from ..._internal.config_parsing.call_by import ParsedCallBy, ScalimCallByParseError, parse_call_by
from ..._internal.config_parsing.field_extract import ScalimFieldExtractCompileError, compile_field_extract
from ..._internal.config_parsing.security import SecureComputeEngine, is_constant_compute_expression
from ...params_template import CompiledParamsTemplate, ScalimParamsTemplateCompileError, compile_params_template
from ...reference_syntax import (
    BUILTIN_CALLABLE_REFERENCE_PREFIX,
    ScalimReferenceSyntaxError,
    is_valid_builtin_callable_reference,
    parse_python_reference,
)
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
from .conversion_bindings import ConfigToIRConversionBindingMixin
from .conversion_lookup import CALL_BY_CTX_KEY, validate_source_id
from .conversion_relations import ConfigToIRConversionRelationMixin

if TYPE_CHECKING:
    from .....spec.ir import LookupStepIr
    from .....spec.ir._source_normalize import NormalizeOnConflict, NormalizeOnEmpty, NormalizeOnMissing, NormalizeOnNone
    from .....vendor.compact.typing_extensionsx import TypeGuard


def _ensure_field_value(value: RuntimeValue, *, field_id: str, producer: str) -> FieldValue:
    if value is None or isinstance(value, FIELD_VALUE_TYPES):
        return value
    msg = "Field '{}' {} has unsupported value type '{}'; expected {}".format(
        field_id,
        producer,
        type(value).__name__,
        format_field_value_expected_types(),
    )
    raise TypeError(msg)


def _is_normalize_on_conflict(value: str) -> "TypeGuard[NormalizeOnConflict]":
    return value in {"error", "first", "last"}


def _is_normalize_on_none(value: str) -> "TypeGuard[NormalizeOnNone]":
    return value in {"raise", "skip"}


def _is_normalize_on_empty(value: str) -> "TypeGuard[NormalizeOnEmpty]":
    return value in {"miss", "null", "error"}


def _is_normalize_on_missing(value: str) -> "TypeGuard[NormalizeOnMissing]":
    return value in {"error", "null"}


def _parse_callable_ref(reference: Any, *, context_label: str) -> CallableRefIr:
    raw = str(reference or "").strip()
    if not raw:
        msg = "{} must not be empty".format(context_label)
        raise ScalimConversionError(msg)

    if raw.startswith(BUILTIN_CALLABLE_REFERENCE_PREFIX):
        if not is_valid_builtin_callable_reference(raw):
            msg = "{} has invalid builtin callable reference: {!r}".format(context_label, raw)
            raise ScalimConversionError(msg)
        return BuiltinCallableIdIr(callable_id=raw[len(BUILTIN_CALLABLE_REFERENCE_PREFIX) :])

    try:
        parsed = parse_python_reference(raw)
    except ScalimReferenceSyntaxError as exc:
        raise ScalimConversionError(str(exc)) from exc

    return PythonReferenceIr(
        reference=str(parsed.reference),
        module_path=str(parsed.module_path),
        attr_path=tuple(str(x) for x in parsed.attr_path),
        style=str(parsed.style),
    )


def _convert_call_by_value_ir(value: Any, *, field_id: str) -> CallByValueIr:
    kind = getattr(value, "kind", None)  # pragma: allow-dynattr dsl: parsed call_by value contract
    raw = getattr(value, "value", None)  # pragma: allow-dynattr dsl: parsed call_by value contract
    kind_text = str(kind or "").strip()
    if kind_text == "literal":
        typed = _ensure_field_value(raw, field_id=field_id, producer="call_by literal")
        return CallByValueIr(kind="literal", value=typed)
    if kind_text == "field":
        return CallByValueIr(kind="field", value=str(raw))
    if kind_text == "ctx":
        return CallByValueIr(kind="ctx", value="")
    if kind_text == "ctx_attr":
        return CallByValueIr(kind="ctx_attr", value=str(raw))
    msg = "Derived field '{}' has unknown call_by value kind: {!r}".format(field_id, kind_text)
    raise ScalimConversionError(msg)


def _convert_parsed_call_by_spec(
    parsed: ParsedCallBy,
    *,
    field_id: str,
    context_label: Optional[str] = None,
) -> CallBySpecIr:
    ref = _parse_callable_ref(parsed.reference, context_label=context_label or "derived_fields.{}.call_by reference".format(field_id))
    args = tuple(_convert_call_by_value_ir(item, field_id=field_id) for item in parsed.args)
    kwargs = tuple((str(key), _convert_call_by_value_ir(item, field_id=field_id)) for key, item in parsed.kwargs)
    field_names = tuple(str(x) for x in parsed.field_names)
    return CallBySpecIr(
        reference=ref,
        args=args,
        kwargs=kwargs,
        field_names=field_names,
    )


class ConfigToIRConversionSourceMixin(ConfigToIRConversionBindingMixin, ConfigToIRConversionRelationMixin):
    _compute_engine: Optional[SecureComputeEngine] = None
    _init_vars: Optional[Mapping[str, RuntimeValue]] = None

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

        loader_ref = _parse_callable_ref(config.loader, context_label="main_source.loader")
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

        params: StaticParams = {}
        if not template.is_empty_mapping():
            params = template.render_kwargs(_build_main_source_context(config.source_id), path="main_source.params")

        return MainSourceIr(
            source_id=config.source_id,
            loader_ref=loader_ref,
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
        loader_ref = _parse_callable_ref(source_config.loader, context_label="sources.{}.loader".format(source_config.source_id))

        lookup_cast_spec = None
        if source_config.lookup_cast is not None:
            lookup_cast_spec = self._get_lookup_cast_spec(source_config.lookup_cast)

        key_ir = KeyIr(key=source_config.key, cast=lookup_cast_spec)

        normalize_ir = self._convert_source_normalize(source_config)

        loader_ir = self._make_loader_ir(callable_ref=loader_ref)

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

        call_by_ref = self._convert_source_normalize_call_by_ref(norm, source_id=source_id)

        if kind == "index_by_key":
            return self._convert_source_normalize_index_by_key(source_config, norm=norm, call_by_ref=call_by_ref)
        if kind == "take_first":
            return self._convert_source_normalize_take_first(source_id=source_id, norm=norm, call_by_ref=call_by_ref)
        if kind == "project_fields":
            return self._convert_source_normalize_project_fields(source_id=source_id, norm=norm, call_by_ref=call_by_ref)
        if kind == "map_values":
            return self._convert_source_normalize_map_values(source_id=source_id, norm=norm, call_by_ref=call_by_ref)

        msg = "sources.{}.normalize.kind must be one of: index_by_key/take_first/project_fields/map_values".format(
            source_id
        )  # pragma: no cover  # pragma: allow-no-cover invariant: normalize kind validated above
        raise ScalimConversionError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: normalize kind validated above

    def _convert_source_normalize_call_by_ref(
        self,
        norm: NormalizeConfig,
        *,
        source_id: str,
    ) -> Optional[CallableRefIr]:
        if norm.call_by is None:
            return None

        call_by_ref = str(norm.call_by or "").strip()
        if not call_by_ref:
            msg = "sources.{}.normalize.call_by must not be empty".format(source_id)
            raise ScalimConversionError(msg)
        return _parse_callable_ref(call_by_ref, context_label="sources.{}.normalize.call_by".format(source_id))

    def _convert_source_normalize_index_by_key(
        self,
        source_config: SourceConfig,
        *,
        norm: NormalizeConfig,
        call_by_ref: Optional[CallableRefIr],
    ) -> SourceNormalizeIr:
        source_id = source_config.source_id

        on_conflict = str(norm.on_conflict or "error").strip() or "error"
        if not _is_normalize_on_conflict(on_conflict):
            msg = "sources.{}.normalize.on_conflict must be one of: error/first/last".format(source_id)
            raise ScalimConversionError(msg)

        on_none = str(norm.on_none or "raise").strip() or "raise"
        if not _is_normalize_on_none(on_none):
            msg = "sources.{}.normalize.on_none must be one of: raise/skip".format(source_id)
            raise ScalimConversionError(msg)

        if isinstance(source_config.key, tuple):
            msg = "sources.{}.normalize.kind=index_by_key does not support composite key yet".format(source_id)
            raise ScalimConversionError(msg)

        declared_key = str(source_config.key or "").strip()
        if not declared_key:
            msg = "sources.{}.key must be a non-empty string".format(source_id)
            raise ScalimConversionError(msg)

        key_field = str(norm.key_field or "").strip()
        if key_field:
            if declared_key != key_field:
                msg = "sources.{}.normalize.key_field must equal sources.{}.key".format(source_id, source_id)
                raise ScalimConversionError(msg)
        else:
            key_field = declared_key

        return SourceNormalizeIr(
            kind="index_by_key",
            key_field=key_field,
            on_conflict=on_conflict,
            on_none=on_none,
            call_by_ref=call_by_ref,
        )

    def _convert_source_normalize_take_first(
        self,
        *,
        source_id: str,
        norm: NormalizeConfig,
        call_by_ref: Optional[CallableRefIr],
    ) -> SourceNormalizeIr:
        on_empty = str(norm.on_empty or "miss").strip() or "miss"
        if not _is_normalize_on_empty(on_empty):
            msg = "sources.{}.normalize.on_empty must be one of: miss/null/error".format(source_id)
            raise ScalimConversionError(msg)
        return SourceNormalizeIr(kind="take_first", on_empty=on_empty, call_by_ref=call_by_ref)

    def _convert_source_normalize_project_fields(
        self,
        *,
        source_id: str,
        norm: NormalizeConfig,
        call_by_ref: Optional[CallableRefIr],
    ) -> SourceNormalizeIr:
        on_missing = str(norm.on_missing or "error").strip() or "error"
        if not _is_normalize_on_missing(on_missing):
            msg = "sources.{}.normalize.on_missing must be one of: error/null".format(source_id)
            raise ScalimConversionError(msg)

        fields = self._convert_source_normalize_project_fields_rules(
            norm.fields,
            config_path="sources.{}.normalize.fields".format(source_id),
        )
        return SourceNormalizeIr(kind="project_fields", fields=fields, on_missing=on_missing, call_by_ref=call_by_ref)

    def _convert_source_normalize_map_values(
        self,
        *,
        source_id: str,
        norm: NormalizeConfig,
        call_by_ref: Optional[CallableRefIr],
    ) -> SourceNormalizeIr:
        steps = norm.steps
        if not steps:
            msg = "sources.{}.normalize.steps must not be empty".format(source_id)
            raise ScalimConversionError(msg)

        converted_steps: List[SourceNormalizeStepIr] = []
        for idx, step in enumerate(steps):
            converted_steps.append(self._convert_source_normalize_step(step, source_id=source_id, idx=idx))

        return SourceNormalizeIr(kind="map_values", steps=tuple(converted_steps), call_by_ref=call_by_ref)

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
            if not _is_normalize_on_empty(step_on_empty):
                msg = "{}.on_empty must be one of: miss/null/error".format(step_path)
                raise ScalimConversionError(msg)
            return SourceNormalizeStepIr(kind="take_first", on_empty=step_on_empty)

        if step_kind == "project_fields":
            step_on_missing = str(step.on_missing or "error").strip() or "error"
            if not _is_normalize_on_missing(step_on_missing):
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
        rules: Mapping[str, Any],
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
        rule_obj: Any,
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

    def _make_loader_ir(self, callable_ref: CallableRefIr) -> LoaderIr:
        return LoaderIr(callable_ref=callable_ref, bindings={})

    def _resolve_field_source(self, *, from_source_id: str, field_id: str) -> SourceRefIr:
        if self._main_source_ir is not None and from_source_id == self._main_source_ir.source_id:
            return self._main_source_ir

        source_ir = self._require_sources_ir().get(from_source_id)
        if source_ir is None:
            msg = "Field '{}' references unknown source '{}'".format(field_id, from_source_id)
            raise ScalimConversionError(msg)
        return source_ir

    def _convert_source_field(self, field_config: SourceFieldConfig, config: DemandConfig) -> FieldIr:  # noqa: C901, PLR0912, PLR0915  # pragma: allow-c901 plan: c0
        from_source_id = field_config.source
        main_source_id = config.main_source.source_id
        if from_source_id == main_source_id:
            base_path = "main_source.fields.{}".format(field_config.field_id)
        else:
            base_path = "sources.{}.fields.{}".format(from_source_id, field_config.field_id)

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

        value_ops: Tuple[ValueOpIr, ...] = ()
        if field_config.value_cast:
            value_ops = (self._get_value_cast_op(field_config.value_cast),)

        lookup_steps: Optional[Tuple["LookupStepIr", ...]] = None
        if isinstance(source_ir, SourceIr):
            lookup_steps = self._resolve_lookup_steps(field_config, config, source_ir)

        default_cases: Tuple[FieldDefaultCaseIr, ...] = ()
        if field_config.default is not None:
            if lookup_steps is None:
                msg = "Field '{}' default is only allowed for ref fields (requires relation)".format(field_config.field_id)
                raise ScalimConversionError(msg)

            converted_default_cases: List[FieldDefaultCaseIr] = []
            for idx, case in enumerate(field_config.default):
                when = str(case.get("when") or "").strip()
                if when != "relation_miss":
                    msg = "Field '{}' default[{}] has unsupported when={!r} (v1 only supports 'relation_miss')".format(
                        field_config.field_id,
                        int(idx),
                        when,
                    )
                    raise ScalimConversionError(msg)

                if "literal" in case:
                    literal_val = _ensure_field_value(case.get("literal"), field_id=field_config.field_id, producer="default literal")
                    converted_default_cases.append(
                        FieldDefaultCaseIr(
                            when="relation_miss",
                            kind="literal",
                            literal=literal_val,
                            call_by=None,
                        )
                    )
                    continue

                call_by_raw = case.get("call_by")
                try:
                    parsed_call_by = parse_call_by(call_by_raw)
                except ScalimCallByParseError as exc:
                    msg = "Field '{}' default[{}] has invalid call_by: {}".format(field_config.field_id, int(idx), exc)
                    raise ScalimConversionError(msg) from exc

                reference = str(parsed_call_by.reference or "").strip()
                if reference == "^defaults/zero_of_value_cast":
                    msg = (
                        "Field '{}' default[{}] uses removed builtin '{}()'; "
                        "use '^defaults/default()' (or '^defaults/default_of_value_cast()') instead"
                    ).format(field_config.field_id, int(idx), reference)
                    raise ScalimConversionError(msg)

                if reference in ("^defaults/default_of_value_cast", "^defaults/default") and not field_config.value_cast:
                    msg = ("Field '{}' default[{}] uses '{}()' which requires explicit value_cast; add value_cast or use literal").format(
                        field_config.field_id, int(idx), reference
                    )
                    raise ScalimConversionError(msg)

                call_by_spec = _convert_parsed_call_by_spec(
                    parsed_call_by,
                    field_id=field_config.field_id,
                    context_label="{}.default[{}].call_by reference".format(base_path, int(idx)),
                )
                converted_default_cases.append(
                    FieldDefaultCaseIr(
                        when="relation_miss",
                        kind="call_by",
                        call_by=call_by_spec,
                    )
                )

            default_cases = tuple(converted_default_cases)

        return FieldIr(
            field_id=field_config.field_id,
            name=field_config.name or field_config.field_id,
            source=source_ir,
            data_key=data_key,
            extract_expr=extract_expr,
            extract_segments=extract_segments,
            is_primary=False,
            value_ops=value_ops,
            relation=None,
            lookup_steps=lookup_steps,
            default_cases=default_cases,
        )

    def _convert_derived_field(self, derived_config: DerivedFieldConfig) -> DerivedFieldIr:
        call_ctx_key: Optional[str] = None
        is_constant_compute = False
        compute_expr = ""
        call_by_spec: Optional[CallBySpecIr] = None

        if derived_config.compute:
            compute_expr = str(derived_config.compute or "").strip()
            # 静态校验: 不产生用户导入,仅验证表达式语法与安全约束.
            _ = self._require_compute_engine().compile(compute_expr, derived_config.depends_on)
            if not derived_config.depends_on and is_constant_compute_expression(compute_expr):
                is_constant_compute = True
        elif derived_config.call_by:
            try:
                parsed = parse_call_by(derived_config.call_by)
            except ScalimCallByParseError as exc:
                msg = "Derived field '{}' has invalid call_by: {}".format(derived_config.field_id, exc)
                raise ScalimConversionError(msg) from exc

            call_by_spec = _convert_parsed_call_by_spec(parsed, field_id=derived_config.field_id)
            if call_by_requires_ctx(call_by_spec):
                call_ctx_key = CALL_BY_CTX_KEY
        else:
            msg = "Derived field '{}' must declare 'compute' or 'call_by'".format(derived_config.field_id)
            raise ScalimConversionError(msg)

        return DerivedFieldIr(
            field_id=derived_config.field_id,
            name=derived_config.name,
            dependencies=derived_config.depends_on,
            compute_expr=compute_expr,
            call_by=call_by_spec,
            call_ctx_key=call_ctx_key,
            is_constant_compute=is_constant_compute,
        )


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

    return BindingIr(
        key_field=key_field,
        params_template=template,
        mode=mode,
        as_=as_mode,
        cache_mode=cache_mode,
        param_name=None,
        template_path=path,
    )


__all__ = ()
