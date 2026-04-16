# pragma: allow-c901-file plan: c70
"""`YAML DSL` 运行时编译器.

本模块将 `YAML DSL` 文件转换为:
- 已校验的配置(`DemandConfig`)
- 中间表示(`DemandIr`)
- 运行时请求(`ExecutionRequest`)
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ....events import generate_run_id
from ....execution.guardrails import GuardrailsPolicy
from ....execution.loader_retry import LoaderRetryPolicies, LoaderRetryPoliciesSpec, LoaderRetryPolicy, LoaderRetryPolicySpec
from ....execution.run_ir import ExecutionRequest, ObservabilitySpec, OutputSpec, export_layout_from_demand_ir
from ....spec.ir import DemandIr
from ....vendor.dataclassesx import replace
from .._internal.config_parsing.loader import YamlDemandLoader
from .._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from .._internal.validation_contracts import validate_output_name as _validate_output_name_ssot
from ..diagnostics import format_duplicate_effective_field_display_names_message
from ..init_var_nodes import parse_init_var_mapping_node
from ..reference_syntax import BUILTIN_CALLABLE_REFERENCE_PREFIX
from ..schema_dsl.constants import DEFAULT_OUTPUT_ENCODING
from ..schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    FileConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
    ResourcesConfig,
)
from ..schema_dsl.output_enums import (
    BOOK_KINDS,
    BOOK_WRITE_ALIGN_BY_ENUM,
    BOOK_WRITE_HEADER_POLICY_ENUM,
    BOOK_WRITE_MODE_ENUM,
    BOOK_WRITE_ON_CONFLICT_ENUM,
    BOOK_WRITE_ON_MISMATCH_ENUM,
    DEFAULT_BOOK_WRITE_ALIGN_BY,
    DEFAULT_BOOK_WRITE_HEADER_POLICY,
    DEFAULT_BOOK_WRITE_MODE,
    DEFAULT_BOOK_WRITE_ON_CONFLICT,
    DEFAULT_BOOK_WRITE_ON_MISMATCH,
    FILE_KINDS,
)
from ._internal.callable_preflight import validate_signature_accepts_any_candidate
from .builtin_callables import parse_builtin_callable_id
from .contracts import (
    BookBudgetOverride,
    BookExportXlsxOverride,
    BookResourceOverride,
    BookWriteDefaultsOverride,
    CaptureRows,
    Compilation,
    DemandRunOptions,
    FileResourceOverride,
    OutputExtraSheetOverride,
    OutputExtrasOverride,
    OutputOverride,
    OutputsDefaultsOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResolverTrustedMode,
    ResourcesOverride,
    UnsetType,
)
from .conversion import ConfigToIRConverter
from .effective_outputs import outputs_require_unique_effective_field_display_names
from .errors import ALLOWLIST_REQUIRED_MSG, ScalimAllowlistRequiredError, ScalimResolverError
from .output_composition_yaml import compile_output_composition_from_yaml
from .references import SecurePythonReferenceResolver, derive_base_module_path
from .runtime_linking import resolve_runtime_bindings

if TYPE_CHECKING:
    from ....execution.output_composition import OutputCompositionSpec
    from ....execution.runtime_bindings import RuntimeBindings


def _ensure_allowlist(
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]],
) -> None:
    if not allowed_modules and not allowed_functions:
        # 安全审计:仅允许从 `allowlist` 中指定的模块/函数加载,避免 `YAML` 触发任意导入执行.
        raise ScalimAllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)


def validate_allowlist(
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]],
) -> None:
    _ensure_allowlist(allowed_modules, allowed_functions)


_OUTPUT_HEADER_BY_ENUM: Tuple[str, ...] = ("field_id", "name")

_DEMAND_FAILURE_POLICIES: Tuple[str, ...] = ("all_fail", "primary_only")


def _parse_overrides_outputs_defaults_book_id(defaults: Optional[object], *, path: str) -> Optional[str]:
    if defaults is None:
        return None
    if not isinstance(defaults, OutputsDefaultsOverride):
        msg = "{} must be an OutputsDefaultsOverride".format(path)
        raise TypeError(msg)
    book_id = str(defaults.to.book or "").strip()
    if not book_id:
        msg = "{}.to.book is required".format(path)
        raise ValueError(msg)
    return book_id


def _apply_default_book_binding_to_outputs(
    outputs: Tuple[OutputTargetConfig, ...],
    *,
    default_book_id: str,
) -> Tuple[OutputTargetConfig, ...]:
    if not outputs:
        return outputs
    if not default_book_id:
        return outputs

    updated: List[OutputTargetConfig] = []
    for out_cfg in outputs:
        to_cfg = out_cfg.to
        if to_cfg is None:
            updated.append(replace(out_cfg, to=OutputToConfig(book=str(default_book_id))))
            continue

        file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
        book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
        if file_id or book_id:
            updated.append(out_cfg)
            continue

        updated.append(replace(out_cfg, to=replace(to_cfg, book=str(default_book_id))))

    return tuple(updated)


def _parse_typed_overrides_output_to(raw: OutputToOverride) -> OutputToConfig:
    file_id = str(raw.file or "").strip() if raw.file is not None else None
    book_id = str(raw.book or "").strip() if raw.book is not None else None
    sheet = str(raw.sheet or "").strip() if raw.sheet is not None else None
    if file_id == "":
        file_id = None
    if book_id == "":
        book_id = None
    if sheet == "":
        sheet = None

    return OutputToConfig(file=file_id, book=book_id, sheet=sheet)


def _parse_typed_overrides_output_write(raw: OutputWriteOverride, *, path: str) -> OutputWriteConfig:
    def _as_opt_str(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        v = str(value).strip()
        return v or None

    include_header = raw.include_header
    if include_header is not None and not isinstance(include_header, bool):
        msg = "{}.include_header must be a boolean".format(path)
        raise TypeError(msg)

    header_fields_output_by = _as_opt_str(raw.header_fields_output_by)
    if header_fields_output_by is not None and header_fields_output_by not in _OUTPUT_HEADER_BY_ENUM:
        msg = "{}.header_fields_output_by={!r} is invalid; expected one of: {}".format(
            path, header_fields_output_by, ", ".join(_OUTPUT_HEADER_BY_ENUM)
        )
        raise ValueError(msg)

    return OutputWriteConfig(include_header=include_header, header_fields_output_by=header_fields_output_by)


def _apply_demand_runtime_policy_overrides(config: DemandConfig, *, options: DemandRunOptions) -> DemandConfig:
    next_config = config

    if not isinstance(options.runtime.batch_size, UnsetType):
        raw = options.runtime.batch_size
        if raw is None:
            next_config = replace(next_config, batch_size=None)
        else:
            if isinstance(raw, bool) or not isinstance(raw, int):
                msg = "batch_size must be an integer >= 1 or None"
                raise TypeError(msg)
            if int(raw) < 1:
                msg = "batch_size must be >= 1 when provided"
                raise ValueError(msg)
            next_config = replace(next_config, batch_size=int(raw))

    if options.runtime.demand_failure_policy is not None:
        normalized = str(options.runtime.demand_failure_policy or "").strip()
        if normalized not in _DEMAND_FAILURE_POLICIES:
            msg = "demand_failure_policy={!r} is invalid; expected one of: {}".format(normalized, ", ".join(_DEMAND_FAILURE_POLICIES))
            raise ValueError(msg)
        next_config = replace(next_config, failure_policy=str(normalized))

    demand_diagnostics = options.runtime.demand_diagnostics
    if demand_diagnostics is not None:
        next_config = replace(
            next_config,
            include_full_error_message=bool(demand_diagnostics.include_full_error_message),
            validate_unique_field_names=bool(demand_diagnostics.validate_unique_field_names),
        )

    return next_config


def _parse_output_extra_sheet_override(
    raw: object,
    *,
    path: str,
) -> Optional[OutputExtraSheetConfig]:
    if raw is None:
        return None
    if isinstance(raw, bool):
        if not raw:
            return None
        return OutputExtraSheetConfig()
    if not isinstance(raw, OutputExtraSheetOverride):
        msg = "{} must be a boolean or an OutputExtraSheetOverride".format(path)
        raise TypeError(msg)

    sheet = str(raw.sheet).strip() if raw.sheet is not None else None

    raw_path = raw.path
    if raw_path is not None and not isinstance(raw_path, (str, os.PathLike)):
        msg = "{}.path must be a string or PathLike".format(path)
        raise TypeError(msg)
    resolved_path = str(raw_path) if raw_path is not None else None

    allow_formulas = raw.allow_formulas
    if allow_formulas is not None and not isinstance(allow_formulas, bool):
        msg = "{}.allow_formulas must be a bool".format(path)
        raise TypeError(msg)

    return OutputExtraSheetConfig(
        path=resolved_path,
        sheet=sheet,
        allow_formulas=allow_formulas,
    )


def _apply_output_extras_overrides(config: DemandConfig, *, options: DemandRunOptions) -> DemandConfig:
    overrides = options.outputs.overrides
    if overrides is None or overrides.output_extras is None:
        return config
    extras = overrides.output_extras
    if not isinstance(extras, OutputExtrasOverride):
        msg = "overrides.output_extras must be an OutputExtrasOverride"
        raise TypeError(msg)

    meta = _parse_output_extra_sheet_override(extras.meta, path="overrides.output_extras.meta")
    audit = _parse_output_extra_sheet_override(extras.audit, path="overrides.output_extras.audit")
    return replace(config, meta=meta, audit=audit)


def _parse_overrides_outputs_targets(  # noqa: C901, PLR0912, PLR0915
    overrides: Sequence[OutputOverride],
    demand_ir: DemandIr,
    *,
    path: str,
    default_book_id: Optional[str],
    default_book_ref: str,
) -> Tuple[OutputTargetConfig, ...]:
    if not isinstance(overrides, tuple) and not isinstance(overrides, list):
        msg = "{} must be a sequence of OutputOverride".format(path)
        raise TypeError(msg)
    if not overrides:
        msg = "{} cannot be empty".format(path)
        raise ValueError(msg)

    known_field_ids: Set[str] = {str(fid) for fid in demand_ir.fields}
    seen_names: Set[str] = set()
    parsed: List[OutputTargetConfig] = []

    for idx, item in enumerate(overrides):
        if not isinstance(item, OutputOverride):
            msg = "{}.{} must be an OutputOverride".format(path, idx)
            raise TypeError(msg)

        name = str(item.name or "").strip()
        _validate_output_name_ssot(name, path="{}.{}.name".format(path, idx))
        if name in seen_names:
            msg = "{} has duplicate output name: {}".format(path, name)
            raise ValueError(msg)
        seen_names.add(name)

        fields = item.fields
        if not isinstance(fields, tuple):
            msg = "{}.{}.fields must be a tuple[str, ...]".format(path, idx)
            raise TypeError(msg)
        if not fields:
            msg = "{}.{}.fields must not be empty".format(path, idx)
            raise ValueError(msg)

        field_ids: List[str] = []
        for field_idx, field_id_raw in enumerate(fields):
            if not isinstance(field_id_raw, str):
                msg = "{}.{}.fields.{} must be a field_id string".format(path, idx, field_idx)
                raise TypeError(msg)
            field_id = field_id_raw.strip()
            if not field_id:
                msg = "{}.{}.fields.{} must not be empty".format(path, idx, field_idx)
                raise ValueError(msg)
            field_ids.append(field_id)

        unknown_fields = [fid for fid in field_ids if fid not in known_field_ids]
        if unknown_fields:
            msg = "{}.{}.fields reference unknown fields: {}".format(path, idx, ", ".join(sorted(set(unknown_fields))))
            raise ValueError(msg)

        to_override = item.to
        if not isinstance(to_override, OutputToOverride):
            msg = "{}.{}.to must be an OutputToOverride".format(path, idx)
            raise TypeError(msg)
        to_cfg = _parse_typed_overrides_output_to(to_override)

        write_cfg = None
        if item.write is not None:
            write_override = item.write
            if not isinstance(write_override, OutputWriteOverride):
                msg = "{}.{}.write must be an OutputWriteOverride".format(path, idx)
                raise TypeError(msg)
            write_cfg = _parse_typed_overrides_output_write(write_override, path="{}.{}.write".format(path, idx))

        file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
        book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
        sheet = str(to_cfg.sheet or "").strip() if to_cfg.sheet is not None else ""

        if file_id:
            if book_id:
                msg = "{}.{}.to must declare exactly one of to.file or to.book".format(path, idx)
                raise ValueError(msg)
            if sheet:
                msg = "{}.{}.to.sheet is not allowed with to.file".format(path, idx)
                raise ValueError(msg)
        else:
            effective_book_id = book_id or str(default_book_id or "").strip()
            if not effective_book_id:
                msg = ("Missing output destination for {}.{}.to; set {}.{}.to.book explicitly or provide {}.").format(
                    path, idx, path, idx, default_book_ref
                )
                raise ValueError(msg)
            if book_id != effective_book_id:
                to_cfg = replace(to_cfg, book=str(effective_book_id))
                book_id = effective_book_id

        parsed.append(
            OutputTargetConfig(
                name=str(name),
                from_=None,
                to=to_cfg,
                write=write_cfg,
                fields=tuple(field_ids),
                where=None,
                aggregate=None,
                requires=(),
            )
        )

    return tuple(parsed)


def _should_validate_unique_effective_field_display_names(config: DemandConfig, outputs: Tuple[OutputTargetConfig, ...]) -> bool:
    if not bool(config.validate_unique_field_names):
        return False
    return outputs_require_unique_effective_field_display_names(config, outputs=outputs, resources_override=None)


def _validate_unique_effective_field_display_names(demand_ir: DemandIr) -> None:
    conflicts: Dict[str, List[str]] = {}
    for field_id, field_ir in demand_ir.fields.items():
        name = str(field_ir.name or "").strip()
        effective = name or str(field_id)
        conflicts.setdefault(effective, []).append(str(field_id))

    duplicates = {name: ids for name, ids in conflicts.items() if len(ids) > 1}
    if not duplicates:
        return

    msg = format_duplicate_effective_field_display_names_message(duplicates)
    raise ValueError(msg)


def _merge_retry_specs(base: LoaderRetryPolicySpec, override: Optional[LoaderRetryPolicySpec]) -> LoaderRetryPolicySpec:
    if override is None:
        return base
    return LoaderRetryPolicySpec(
        enabled=override.enabled if override.enabled is not None else base.enabled,
        should_retry=override.should_retry if override.should_retry is not None else base.should_retry,
        max_attempts=override.max_attempts if override.max_attempts is not None else base.max_attempts,
        max_elapsed_seconds=override.max_elapsed_seconds if override.max_elapsed_seconds is not None else base.max_elapsed_seconds,
        backoff=override.backoff if override.backoff is not None else base.backoff,
        base_delay_seconds=override.base_delay_seconds if override.base_delay_seconds is not None else base.base_delay_seconds,
        max_delay_seconds=override.max_delay_seconds if override.max_delay_seconds is not None else base.max_delay_seconds,
        jitter=override.jitter if override.jitter is not None else base.jitter,
    )


def _finalize_retry_policy(
    spec: LoaderRetryPolicySpec,
    *,
    base: Optional[LoaderRetryPolicy] = None,
    location: str,
) -> LoaderRetryPolicy:
    base_policy = base or LoaderRetryPolicy.disabled()
    enabled = spec.enabled if spec.enabled is not None else base_policy.enabled
    should_retry = spec.should_retry if spec.should_retry is not None else base_policy.should_retry
    max_attempts = spec.max_attempts if spec.max_attempts is not None else base_policy.max_attempts
    max_elapsed = spec.max_elapsed_seconds if spec.max_elapsed_seconds is not None else base_policy.max_elapsed_seconds
    backoff = spec.backoff if spec.backoff is not None else base_policy.backoff
    base_delay = spec.base_delay_seconds if spec.base_delay_seconds is not None else base_policy.base_delay_seconds
    max_delay = spec.max_delay_seconds if spec.max_delay_seconds is not None else base_policy.max_delay_seconds
    jitter = spec.jitter if spec.jitter is not None else base_policy.jitter

    if enabled and should_retry is None:
        msg = "loader_retry.enabled=true requires should_retry (provide via runtime injection)"
        raise ValueError(msg)

    if enabled and should_retry is not None:
        # 编译期签名预检查: 避免运行期 `_safe_should_retry` 将 `TypeError` 静默降级为 `False`.
        placeholder_exc = object()
        placeholder_ctx = object()
        empty_kwargs: Dict[str, object] = {}
        candidates = (("should_retry(exc, ctx)", (placeholder_exc, placeholder_ctx), empty_kwargs),)
        ref = repr(should_retry)
        try:
            module = should_retry.__module__
            name = should_retry.__name__
        except AttributeError:
            pass
        else:
            ref = "{}:{}".format(module, name)
        validate_signature_accepts_any_candidate(
            location="{}.should_retry".format(str(location)),
            reference=ref,
            fn=should_retry,
            candidates=candidates,
            hint="should_retry 必须支持位置参数调用形态 `should_retry(exc, ctx)` (当签名可 introspect 时)",
        )

    return LoaderRetryPolicy(
        enabled=bool(enabled),
        should_retry=should_retry,
        max_attempts=int(max_attempts),
        max_elapsed_seconds=float(max_elapsed),
        backoff=str(backoff),
        base_delay_seconds=float(base_delay),
        max_delay_seconds=float(max_delay),
        jitter=bool(jitter),
    )


def _compile_loader_retry_policies(
    config: DemandConfig,
    *,
    overrides: Optional[LoaderRetryPoliciesSpec],
) -> Optional[LoaderRetryPolicies]:
    if overrides is None:
        return None
    base_policy = LoaderRetryPolicy.disabled()
    global_spec = overrides.default or LoaderRetryPolicySpec()
    global_policy = _finalize_retry_policy(global_spec, base=base_policy, location="loader_retry.default")

    known_loaders = set(config.sources.keys())
    known_loaders.add(config.main_source.source_id)
    if overrides.by_loader:
        unknown = set(overrides.by_loader.keys()) - known_loaders
        if unknown:
            msg = "Unknown loader_retry.by_loader keys: {}".format(", ".join(sorted(unknown)))
            raise ValueError(msg)

    by_loader: Dict[str, LoaderRetryPolicy] = {}

    main_source_id = config.main_source.source_id
    main_driver = overrides.by_loader.get(main_source_id)
    main_spec = _merge_retry_specs(global_spec, main_driver)
    main_policy = _finalize_retry_policy(main_spec, base=base_policy, location="loader_retry.by_loader.{}".format(main_source_id))
    if main_policy != global_policy:
        by_loader[main_source_id] = main_policy

    for source_id in config.sources:
        src_driver = overrides.by_loader.get(source_id)
        src_spec = _merge_retry_specs(global_spec, src_driver)
        src_policy = _finalize_retry_policy(src_spec, base=base_policy, location="loader_retry.by_loader.{}".format(source_id))
        if src_policy != global_policy:
            by_loader[source_id] = src_policy

    if not global_policy.enabled and not by_loader:
        return None

    return LoaderRetryPolicies(default=global_policy, by_loader=by_loader)


def load_config(
    yaml_path: str,
    *,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Sequence[str]] = None,
) -> DemandConfig:
    loader = YamlDemandLoader()
    return loader.load(
        yaml_path,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
    )


def _normalize_builtin_callable_id(id_raw: object, *, label: str) -> str:
    builtin_id = str(id_raw or "").strip()
    if not builtin_id:
        msg = "{}: <id> must not be empty".format(label)
        raise ValueError(msg)
    if builtin_id.startswith(BUILTIN_CALLABLE_REFERENCE_PREFIX):
        msg = "{}: <id> must not include prefix '{}': {!r}".format(label, BUILTIN_CALLABLE_REFERENCE_PREFIX, builtin_id)
        raise ValueError(msg)
    try:
        _ = parse_builtin_callable_id(BUILTIN_CALLABLE_REFERENCE_PREFIX + builtin_id)
    except ScalimResolverError as exc:
        msg = "{}: invalid <id> {!r}: {}".format(label, builtin_id, exc)
        raise ValueError(msg) from exc
    return builtin_id


def _compile_builtin_callable_vocab_value(
    builtin_id: str,
    value_raw: object,
    *,
    trusted_resolver: SecurePythonReferenceResolver,
) -> Callable[..., Any]:
    if callable(value_raw):
        return cast("Callable[..., Any]", value_raw)  # pragma: allow-cast callable() typed narrowing

    if isinstance(value_raw, str):
        reference = value_raw.strip()
        if not reference:
            msg = "builtin_callables[{!r}]: value must not be empty".format(builtin_id)
            raise ValueError(msg)
        if reference.startswith(BUILTIN_CALLABLE_REFERENCE_PREFIX):
            msg = "builtin_callables[{!r}]: value must be a Python reference, not builtin '^<id>': {!r}".format(builtin_id, value_raw)
            raise ValueError(msg)
        try:
            return trusted_resolver.resolve(reference)
        except ScalimResolverError as exc:
            msg = "builtin_callables[{!r}]: failed to resolve Python reference {!r}: {}".format(builtin_id, reference, exc)
            raise ValueError(msg) from exc

    msg = "builtin_callables[{!r}]: expected a callable or Python reference string, got: {}".format(builtin_id, type(value_raw).__name__)
    raise TypeError(msg)


def _compile_builtin_callables_vocab(
    builtin_callables: Optional[Mapping[str, object]],
    *,
    allowed_modules: Optional[FrozenSet[str]] = None,
    allowed_functions: Optional[FrozenSet[str]] = None,
) -> Optional[Dict[str, Callable[..., Any]]]:
    if builtin_callables is None:
        return None

    compiled: Dict[str, Callable[..., Any]] = {}
    trusted_resolver = SecurePythonReferenceResolver(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
        base_module_path=None,
    )

    for builtin_id_raw, value_raw in builtin_callables.items():
        builtin_id = _normalize_builtin_callable_id(builtin_id_raw, label="builtin_callables")
        compiled[builtin_id] = _compile_builtin_callable_vocab_value(
            builtin_id,
            value_raw,
            trusted_resolver=trusted_resolver,
        )

    return compiled


def _validate_public_builtin_callable_ids(public_ids: Optional[Sequence[str]]) -> Optional[Tuple[str, ...]]:
    if public_ids is None:
        return None

    validated: List[str] = []
    for raw in public_ids:
        validated.append(_normalize_builtin_callable_id(raw, label="public_builtin_callable_ids"))
    return tuple(validated)


def create_reference_resolver(
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]],
    resolver_trusted_mode: ResolverTrustedMode = ResolverTrustedMode.STRICT_ALLOWLIST,
    base_module_path: Optional[str] = None,
    builtin_callables: Optional[Mapping[str, object]] = None,
    public_builtin_callable_ids: Optional[Sequence[str]] = None,
) -> SecurePythonReferenceResolver:
    compiled_builtin_callables = _compile_builtin_callables_vocab(
        builtin_callables,
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
    )
    validated_public_ids = _validate_public_builtin_callable_ids(public_builtin_callable_ids)
    return SecurePythonReferenceResolver(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
        resolver_trusted_mode=resolver_trusted_mode,
        base_module_path=base_module_path,
        builtin_callables_by_id=compiled_builtin_callables,
        public_builtin_callable_ids=validated_public_ids,
    )


def compile_ir(
    config: DemandConfig,
    *,
    init_vars: Optional[Dict[str, object]] = None,
) -> DemandIr:
    converter = ConfigToIRConverter(init_vars=init_vars)
    return converter.convert(config)


def _resolve_effective_outputs_and_path(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    options: DemandRunOptions,
) -> Tuple[Tuple[OutputTargetConfig, ...], str]:
    overrides = options.outputs.overrides
    overrides_outputs = overrides.outputs if overrides is not None else None
    default_book_id = _parse_overrides_outputs_defaults_book_id(
        None if overrides is None else overrides.outputs_defaults,
        path="overrides.outputs_defaults",
    )
    if overrides_outputs is not None:
        return (
            _parse_overrides_outputs_targets(
                overrides_outputs,
                demand_ir,
                path="overrides.outputs",
                default_book_id=default_book_id,
                default_book_ref="overrides.outputs_defaults.to.book",
            ),
            "overrides.outputs",
        )
    if config.outputs:
        outputs = tuple(config.outputs)
        if default_book_id is not None:
            outputs = _apply_default_book_binding_to_outputs(outputs, default_book_id=str(default_book_id))
        return outputs, "outputs"
    return (), "outputs"


def _normalize_non_empty_pathlike_value(raw: object, *, path: str) -> str:
    if raw is None:
        msg = "{} is required".format(path)
        raise ValueError(msg)
    if isinstance(raw, os.PathLike):
        value = str(os.fspath(raw)).strip()
    elif isinstance(raw, str):
        value = str(raw).strip()
    else:
        msg = "{} must be a string or os.PathLike".format(path)
        raise TypeError(msg)
    if not value:
        msg = "{} is required".format(path)
        raise ValueError(msg)
    return value


def _parse_non_empty_path_or_init_var(raw: object, *, path: str) -> Any:
    if isinstance(raw, dict):
        return {"$init_var": parse_init_var_mapping_node(cast("Dict[str, Any]", raw), path=path)}  # pragma: allow-cast dict narrowing
    if raw is None:
        msg = "{} is required".format(path)
        raise ValueError(msg)
    if not isinstance(raw, os.PathLike) and not isinstance(raw, str):
        msg = "{} must be a non-empty string or {{$init_var: <name>}}".format(path)
        raise TypeError(msg)
    return _normalize_non_empty_pathlike_value(raw, path=path)


def _parse_optional_path_or_init_var(raw: object, *, path: str) -> Any:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return {"$init_var": parse_init_var_mapping_node(cast("Dict[str, Any]", raw), path=path)}  # pragma: allow-cast dict narrowing
    if isinstance(raw, os.PathLike):
        value = str(os.fspath(raw)).strip()
        if not value:
            msg = "{} must not be empty".format(path)
            raise ValueError(msg)
        return value
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            msg = "{} must not be empty".format(path)
            raise ValueError(msg)
        return value
    msg = "{} must be a string or {{$init_var: <name>}}".format(path)
    raise TypeError(msg)


def _normalize_override_mapping_key(raw_id: object, *, path: str) -> str:
    if not isinstance(raw_id, str) or not str(raw_id).strip():
        msg = "{} keys must be non-empty strings".format(path)
        raise ValueError(msg)
    return str(raw_id).strip()


def _overlay_book_write_defaults_override(
    base: Optional[BookWriteDefaultsConfig],
    override: BookWriteDefaultsOverride,
    *,
    path: str,
) -> BookWriteDefaultsConfig:
    base_defaults = base or BookWriteDefaultsConfig(
        mode=str(DEFAULT_BOOK_WRITE_MODE),
        align_by=str(DEFAULT_BOOK_WRITE_ALIGN_BY),
        header_policy=str(DEFAULT_BOOK_WRITE_HEADER_POLICY),
        on_mismatch=str(DEFAULT_BOOK_WRITE_ON_MISMATCH),
        on_conflict=str(DEFAULT_BOOK_WRITE_ON_CONFLICT),
    )

    mode = str(base_defaults.mode or DEFAULT_BOOK_WRITE_MODE) if override.mode is None else str(override.mode).strip()
    align_by = str(base_defaults.align_by or DEFAULT_BOOK_WRITE_ALIGN_BY) if override.align_by is None else str(override.align_by).strip()
    header_policy = (
        str(base_defaults.header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY)
        if override.header_policy is None
        else str(override.header_policy).strip()
    )
    on_mismatch = (
        str(base_defaults.on_mismatch or DEFAULT_BOOK_WRITE_ON_MISMATCH)
        if override.on_mismatch is None
        else str(override.on_mismatch).strip()
    )
    on_conflict = (
        str(base_defaults.on_conflict or DEFAULT_BOOK_WRITE_ON_CONFLICT)
        if override.on_conflict is None
        else str(override.on_conflict).strip()
    )

    validations = (
        ("mode", mode, BOOK_WRITE_MODE_ENUM),
        ("align_by", align_by, BOOK_WRITE_ALIGN_BY_ENUM),
        ("header_policy", header_policy, BOOK_WRITE_HEADER_POLICY_ENUM),
        ("on_mismatch", on_mismatch, BOOK_WRITE_ON_MISMATCH_ENUM),
        ("on_conflict", on_conflict, BOOK_WRITE_ON_CONFLICT_ENUM),
    )
    for key, value, allowed in validations:
        if value not in allowed:
            msg = "Invalid write_defaults.{}={!r}; expected one of: {}".format(str(key), value, ", ".join(allowed))
            err = "{} (path={}.{})".format(msg, path, str(key))
            raise ValueError(err)

    return BookWriteDefaultsConfig(
        mode=str(mode),
        align_by=str(align_by),
        header_policy=str(header_policy),
        on_mismatch=str(on_mismatch),
        on_conflict=str(on_conflict),
    )


def _overlay_book_budget_override(
    base: Optional[BookBudgetConfig],
    override: BookBudgetOverride,
    *,
    path: str,
) -> BookBudgetConfig:
    if base is None:
        if override.max_sheets is None or override.max_total_cells is None:
            msg = "{} requires max_sheets and max_total_cells when creating a new xlsx_memory book".format(path)
            raise ValueError(msg)
        max_sheets = override.max_sheets
        max_total_cells = override.max_total_cells
    else:
        max_sheets = base.max_sheets if override.max_sheets is None else override.max_sheets
        max_total_cells = base.max_total_cells if override.max_total_cells is None else override.max_total_cells

    if isinstance(max_sheets, bool) or not isinstance(max_sheets, int):
        msg = "{}.max_sheets must be an integer".format(path)
        raise TypeError(msg)
    if isinstance(max_total_cells, bool) or not isinstance(max_total_cells, int):
        msg = "{}.max_total_cells must be an integer".format(path)
        raise TypeError(msg)
    if int(max_sheets) < 1:
        msg = "{}.max_sheets must be >= 1".format(path)
        raise ValueError(msg)
    if int(max_total_cells) < 1:
        msg = "{}.max_total_cells must be >= 1".format(path)
        raise ValueError(msg)

    return BookBudgetConfig(max_sheets=int(max_sheets), max_total_cells=int(max_total_cells))


def _overlay_book_export_xlsx_override(
    base: Optional[BookExportXlsxConfig],
    override: BookExportXlsxOverride,
    *,
    path: str,
) -> BookExportXlsxConfig:
    if base is None:
        if override.path is None:
            msg = "{}.path is required when creating export_xlsx".format(path)
            raise ValueError(msg)
        export_path = _parse_non_empty_path_or_init_var(override.path, path="{}.path".format(path))
        return BookExportXlsxConfig(
            path=export_path, allow_formulas=bool(override.allow_formulas) if override.allow_formulas is not None else False
        )

    export_path_any: Any = base.path
    if override.path is not None:
        export_path_any = _parse_non_empty_path_or_init_var(override.path, path="{}.path".format(path))

    allow_formulas = base.allow_formulas if override.allow_formulas is None else bool(override.allow_formulas)
    return BookExportXlsxConfig(path=export_path_any, allow_formulas=bool(allow_formulas))


def _apply_book_override(  # noqa: C901, PLR0912, PLR0915
    base: Optional[BookConfig],
    override: BookResourceOverride,
    *,
    path: str,
) -> BookConfig:
    kind = str(base.kind or "").strip() if base is not None else ""
    book_path: Any = base.path if base is not None else None
    budget = base.budget if base is not None else None
    export_xlsx = base.export_xlsx if base is not None else None
    allow_formulas = bool(base.allow_formulas) if base is not None else False
    write_defaults = base.write_defaults if base is not None else None

    if override.kind is not None:
        kind = str(override.kind or "").strip()
        if not kind:
            msg = "{}.kind must be a non-empty string".format(path)
            raise ValueError(msg)
    if kind not in BOOK_KINDS:
        msg = "{}.kind={!r} is invalid; expected one of: {}".format(path, kind, ", ".join(BOOK_KINDS))
        raise ValueError(msg)

    if override.path is not None:
        book_path = _parse_optional_path_or_init_var(override.path, path="{}.path".format(path))
    if override.allow_formulas is not None:
        if not isinstance(override.allow_formulas, bool):
            msg = "{}.allow_formulas must be a bool".format(path)
            raise TypeError(msg)
        allow_formulas = bool(override.allow_formulas)

    if override.budget is not None:
        budget = _overlay_book_budget_override(budget, override.budget, path="{}.budget".format(path))
    if override.export_xlsx is not None:
        export_xlsx = _overlay_book_export_xlsx_override(export_xlsx, override.export_xlsx, path="{}.export_xlsx".format(path))
    if override.write_defaults is not None:
        write_defaults = _overlay_book_write_defaults_override(
            write_defaults, override.write_defaults, path="{}.write_defaults".format(path)
        )

    if kind == "xlsx_file":
        if override.budget is not None or override.export_xlsx is not None:
            msg = "{}.budget/export_xlsx are not allowed for kind=xlsx_file".format(path)
            raise ValueError(msg)
        if book_path is None:
            msg = "{}.path is required for kind=xlsx_file".format(path)
            raise ValueError(msg)
        if budget is not None:
            msg = "{}.budget is not allowed for kind=xlsx_file".format(path)
            raise ValueError(msg)
        if export_xlsx is not None:
            msg = "{}.export_xlsx is not allowed for kind=xlsx_file".format(path)
            raise ValueError(msg)

    if kind == "xlsx_memory":
        if override.path is not None or override.allow_formulas is not None:
            msg = "{}.path/allow_formulas are not allowed for kind=xlsx_memory (use export_xlsx.*)".format(path)
            raise ValueError(msg)
        if budget is None:
            msg = "{}.budget is required for kind=xlsx_memory".format(path)
            raise ValueError(msg)
        if book_path is not None:
            msg = "{}.path is not allowed for kind=xlsx_memory".format(path)
            raise ValueError(msg)
        if allow_formulas:
            msg = "{}.allow_formulas is not allowed for kind=xlsx_memory".format(path)
            raise ValueError(msg)

    return BookConfig(
        kind=str(kind),
        path=book_path,
        budget=budget,
        export_xlsx=export_xlsx,
        allow_formulas=bool(allow_formulas),
        write_defaults=write_defaults,
    )


def _apply_file_override(base: Optional[FileConfig], override: FileResourceOverride, *, path: str) -> FileConfig:
    kind = str(base.kind or "").strip() if base is not None else ""
    file_path: Any = base.path if base is not None else None
    encoding = str(base.encoding or DEFAULT_OUTPUT_ENCODING) if base is not None else DEFAULT_OUTPUT_ENCODING

    if override.kind is not None:
        kind = str(override.kind or "").strip()
        if not kind:
            msg = "{}.kind must be a non-empty string".format(path)
            raise ValueError(msg)
    if kind not in FILE_KINDS:
        msg = "{}.kind={!r} is invalid; expected one of: {}".format(path, kind, ", ".join(FILE_KINDS))
        raise ValueError(msg)

    if override.path is not None:
        file_path = _parse_optional_path_or_init_var(override.path, path="{}.path".format(path))
    if file_path is None:
        msg = "{}.path is required for kind=csv_file".format(path)
        raise ValueError(msg)

    if override.encoding is not None:
        if not isinstance(override.encoding, str):
            msg = "{}.encoding must be a string".format(path)
            raise TypeError(msg)
        encoding = str(override.encoding).strip() or DEFAULT_OUTPUT_ENCODING
    return FileConfig(kind=str(kind), path=file_path, encoding=str(encoding))


def _apply_resources_override(config: DemandConfig, override: ResourcesOverride) -> DemandConfig:
    if not override.books and not override.files:
        return config

    base_resources = config.resources
    merged_books: Dict[str, BookConfig] = dict(base_resources.books) if base_resources is not None else {}
    merged_files: Dict[str, FileConfig] = dict(base_resources.files) if base_resources is not None else {}

    if override.books:
        for raw_book_id, book_override in override.books.items():
            book_id = _normalize_override_mapping_key(raw_book_id, path="overrides.resources.books")
            if not isinstance(book_override, BookResourceOverride):
                msg = "overrides.resources.books.{} must be a BookResourceOverride".format(book_id)
                raise TypeError(msg)
            merged_books[book_id] = _apply_book_override(
                merged_books.get(book_id),
                book_override,
                path="overrides.resources.books.{}".format(book_id),
            )

    if override.files:
        for raw_file_id, file_override in override.files.items():
            file_id = _normalize_override_mapping_key(raw_file_id, path="overrides.resources.files")
            if not isinstance(file_override, FileResourceOverride):
                msg = "overrides.resources.files.{} must be a FileResourceOverride".format(file_id)
                raise TypeError(msg)
            merged_files[file_id] = _apply_file_override(
                merged_files.get(file_id),
                file_override,
                path="overrides.resources.files.{}".format(file_id),
            )

    return replace(config, resources=ResourcesConfig(books=merged_books, files=merged_files))


def _apply_io_overrides(config: DemandConfig, *, options: DemandRunOptions) -> DemandConfig:
    overrides = options.outputs.overrides
    if overrides is None:
        return config

    next_config = config

    resources_override = overrides.resources
    if resources_override is not None:
        next_config = _apply_resources_override(next_config, resources_override)

    return next_config


def _compile_output_composition_for_outputs(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    effective_outputs: Tuple[OutputTargetConfig, ...],
    outputs_path: str,
    yaml_base_dir: str,
    options: DemandRunOptions,
    resolver: SecurePythonReferenceResolver,
    version_id: str,
) -> Optional["OutputCompositionSpec"]:
    if not effective_outputs:
        return None

    if _should_validate_unique_effective_field_display_names(config, effective_outputs):
        _validate_unique_effective_field_display_names(demand_ir)

    config_for_outputs = config if effective_outputs == tuple(config.outputs) else replace(config, outputs=effective_outputs)
    return cast(  # pragma: allow-cast output composition typed narrowing
        "OutputCompositionSpec",
        compile_output_composition_from_yaml(
            config_for_outputs,
            demand_ir,
            version_id=str(version_id),
            resolver=resolver,
            init_vars=options.template.init_vars,
            yaml_base_dir=str(yaml_base_dir),
            workflow_managed_output_ids=options.outputs.workflow_managed_output_ids,
            outputs_path=outputs_path,
            skip_extra_sheets_without_workbook=(options.outputs.overrides is not None and options.outputs.overrides.outputs is not None),
        ),
    )


def build_request(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    yaml_base_dir: str,
    options: DemandRunOptions,
    resolver: SecurePythonReferenceResolver,
    runtime_bindings: "RuntimeBindings",
) -> ExecutionRequest:
    effective_config = _apply_io_overrides(config, options=options)
    effective_config = _apply_demand_runtime_policy_overrides(effective_config, options=options)
    effective_config = _apply_output_extras_overrides(effective_config, options=options)
    effective_outputs, outputs_path = _resolve_effective_outputs_and_path(effective_config, demand_ir, options=options)
    version_id = str(options.outputs.output_version_id) if options.outputs.output_version_id is not None else generate_run_id()
    output_composition = _compile_output_composition_for_outputs(
        effective_config,
        demand_ir,
        effective_outputs=effective_outputs,
        outputs_path=outputs_path,
        yaml_base_dir=str(yaml_base_dir),
        options=options,
        resolver=resolver,
        version_id=str(version_id),
    )

    # 无 `outputs` 时走默认策略: 不写文件,但 `sink` 仍可捕获数据.
    export_layout = export_layout_from_demand_ir(demand_ir, (), header_fields_output_by="field_id")
    output_spec = OutputSpec(path=None)
    if output_composition is None:
        target_field_ids = list(demand_ir.fields.keys())
        export_layout = export_layout_from_demand_ir(
            demand_ir,
            target_field_ids,
            header_fields_output_by="field_id",
        )

    observability: Optional[ObservabilitySpec] = None
    components = list(options.runtime.components or [])

    if options.outputs.overrides is not None:
        viz_config = options.outputs.overrides.viz_config
        if not isinstance(viz_config, UnsetType) and viz_config is not None:
            observability = ObservabilitySpec(viz_config=viz_config)
    if not components:
        components = None

    guardrails = options.runtime.guardrails or GuardrailsPolicy.disabled()
    loader_retry = _compile_loader_retry_policies(effective_config, overrides=options.runtime.loader_retry)
    batch_size = effective_config.batch_size if isinstance(options.runtime.batch_size, UnsetType) else options.runtime.batch_size

    return ExecutionRequest(
        export_layout=export_layout,
        output=output_spec,
        sink=None,
        output_composition=output_composition,
        observability=observability,
        guardrails=guardrails,
        loader_retry=loader_retry,
        components=components,
        batch_size=batch_size,
        parallel_mode=options.runtime.parallel_mode,
        max_workers=options.runtime.max_workers,
        key_normalization=options.runtime.key_normalization,
        runtime_bindings=runtime_bindings,
        capture_in_memory_rows=isinstance(options.outputs.capture, CaptureRows),
    )


def compile(  # noqa: A001
    yaml_path: str,
    *,
    options: DemandRunOptions,
) -> Compilation:
    validate_allowlist(allowed_modules=options.security.allowed_modules, allowed_functions=options.security.allowed_functions)
    config = load_config(
        yaml_path,
        template_vars=options.template.template_vars,
        template_sandbox=options.template.template_sandbox,
        rendered_yaml_max_len=options.template.rendered_yaml_max_len,
        allowed_yaml_roots=options.security.allowed_yaml_roots,
    )
    config = _apply_demand_runtime_policy_overrides(config, options=options)
    base_module_path = None
    if _config_uses_relative_references(config):
        base_module_path = derive_base_module_path(yaml_path)
    resolver = create_reference_resolver(
        allowed_modules=options.security.allowed_modules,
        allowed_functions=options.security.allowed_functions,
        resolver_trusted_mode=options.security.resolver_trusted_mode,
        base_module_path=base_module_path,
        builtin_callables=options.security.builtin_callables,
        public_builtin_callable_ids=options.security.public_builtin_callable_ids,
    )
    demand_ir = compile_ir(config, init_vars=options.template.init_vars)
    runtime_bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=resolver,
    )
    yaml_base_dir = str(Path(str(yaml_path)).expanduser().resolve(strict=False).parent)
    request = build_request(
        config,
        demand_ir,
        yaml_base_dir=yaml_base_dir,
        options=options,
        resolver=resolver,
        runtime_bindings=runtime_bindings,
    )
    return Compilation(
        config=config,
        demand_ir=demand_ir,
        request=request,
    )


__all__ = (
    "build_request",
    "compile",
    "compile_ir",
    "create_reference_resolver",
    "load_config",
    "validate_allowlist",
)


def _is_relative_reference(value: Optional[str]) -> bool:
    raw = str(value or "").strip()
    return bool(raw) and raw.startswith(".")


def _config_uses_relative_references(config: DemandConfig) -> bool:
    if _is_relative_reference(config.main_source.loader):
        return True

    if any(
        _is_relative_reference(source.loader) or (source.retry is not None and _is_relative_reference(source.retry.should_retry))
        for source in config.sources.values()
    ):
        return True

    if config.retry is not None and _is_relative_reference(config.retry.should_retry):
        return True
    if config.main_source.retry is not None and _is_relative_reference(config.main_source.retry.should_retry):
        return True

    return any(derived.call_by is not None and _is_relative_reference(derived.call_by) for derived in config.derived_fields.values())
