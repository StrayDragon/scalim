"""`YAML DSL` 运行时编译器.

本模块将 `YAML DSL` 文件转换为:
- 已校验的配置(`DemandConfig`)
- 中间表示(`DemandIr`)
- 运行时请求(`ExecutionRequest`)
"""

import os
import re
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ....execution.guardrails import (
    GuardrailMode,
    GuardrailsComputePolicy,
    GuardrailsLoaderPolicy,
    GuardrailsPolicy,
    GuardrailsRelationsPolicy,
)
from ....execution.loader_retry import LoaderRetryPolicies, LoaderRetryPoliciesSpec, LoaderRetryPolicy, LoaderRetryPolicySpec
from ....execution.run_ir import ExecutionRequest, ObservabilitySpec, OutputSpec, export_layout_from_demand_ir
from ....spec.ir.demand import DemandIr
from ....vendor.compact.typing_extensionsx import TypeGuard
from ....vendor.dataclassesx import replace
from ..config_parsing.loader import YamlDemandLoader
from ..init_var_nodes import parse_init_var_mapping_node
from ..reference_syntax import BUILTIN_CALLABLE_REFERENCE_PREFIX
from ..schema_dsl.constants import (
    DEFAULT_OUTPUT_ENCODING,
    DEFAULT_OUTPUT_HEADER_BY,
    DEFAULT_OUTPUT_INCLUDE_HEADER,
    DEFAULT_OUTPUT_STREAMING,
)
from ..schema_dsl.models import DemandConfig, GuardrailsConfig, LoaderRetryConfig, OutputContainerConfig, OutputTargetConfig
from .builtin_callables import parse_builtin_callable_id
from .contracts import Compilation, ResolverTrustedMode, RunOptions, UnsetType
from .conversion import ConfigToIRConverter
from .errors import ALLOWLIST_REQUIRED_MSG, ScalimAllowlistRequiredError, ScalimResolverError
from .observability import compile_observability_spec
from .output_composition_yaml import compile_output_composition_from_yaml
from .references import SecurePythonReferenceResolver, derive_base_module_path

if TYPE_CHECKING:
    from ....execution.output_composition import OutputCompositionSpec


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


_OUTPUT_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_OVERRIDES_OUTPUT_ALLOWED_KEYS: FrozenSet[str] = frozenset(["name", "container", "fields"])
_OVERRIDES_OUTPUT_FORBIDDEN_KEYS: FrozenSet[str] = frozenset(["where", "from", "aggregate"])
_OUTPUT_CONTAINER_TYPES: Tuple[str, ...] = ("workbook", "csv")
_OUTPUT_HEADER_BY_ENUM: Tuple[str, ...] = ("field_id", "name")


def _require_dict(raw: object, *, path: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        msg = "{} must be an object".format(path)
        raise TypeError(msg)
    return cast("Dict[str, Any]", raw)  # pragma: allow-cast runtime dict typed narrowing


def _is_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _parse_overrides_outputs_container_type(container: Dict[str, Any], *, path: str) -> str:
    typ_raw = container.get("type")
    typ = str(typ_raw or "").strip().lower()
    if not typ:
        msg = "{}.type is required".format(path)
        raise ValueError(msg)
    if typ not in _OUTPUT_CONTAINER_TYPES:
        msg = "{}.type={!r} is invalid; expected one of: {}".format(path, typ, ", ".join(_OUTPUT_CONTAINER_TYPES))
        raise ValueError(msg)
    return typ


def _parse_overrides_outputs_container_path(path_raw: Any, *, container_type: str, path: str) -> Any:
    if isinstance(path_raw, dict):
        path_value: Any = {
            "$init_var": parse_init_var_mapping_node(
                cast("Dict[str, Any]", path_raw),  # pragma: allow-cast yaml mapping typed narrowing
                path="{}.path".format(path),
            )
        }
    elif path_raw is None:
        path_value = ""
    elif isinstance(path_raw, os.PathLike):
        path_value = str(os.fspath(path_raw)).strip()
    elif isinstance(path_raw, str):
        path_value = path_raw.strip()
    else:
        msg = "{}.path must be a string (empty allowed for workflow-managed CSV) or {{$init_var: <name>}}".format(path)
        raise TypeError(msg)

    if container_type == "workbook" and not path_value:
        msg = "{}.path is required for workbook outputs".format(path)
        raise ValueError(msg)
    return path_value


def _parse_overrides_outputs_container_header_by(header_by_raw: Any, *, path: str) -> str:
    header_by = str(header_by_raw).strip() if isinstance(header_by_raw, str) else ""
    header_by = (header_by or DEFAULT_OUTPUT_HEADER_BY).strip()
    if header_by not in _OUTPUT_HEADER_BY_ENUM:
        msg = "{}.header_fields_output_by={!r} is invalid; expected one of: {}".format(path, header_by, ", ".join(_OUTPUT_HEADER_BY_ENUM))
        raise ValueError(msg)
    return header_by


def _validate_overrides_outputs_container_semantics(
    container_type: str,
    *,
    path: str,
    sheet: Optional[str],
    streaming: bool,
    allow_formulas: bool,
    write_lock: bool,
) -> None:
    if not streaming:
        msg = "{}.streaming must be true (composed outputs only support streaming=true)".format(path)
        raise ValueError(msg)

    if container_type != "csv":
        return
    if sheet:
        msg = "{}.sheet is only allowed for type=workbook".format(path)
        raise ValueError(msg)
    if allow_formulas:
        msg = "{}.allow_formulas is only allowed for type=workbook".format(path)
        raise ValueError(msg)
    if write_lock:
        msg = "{}.write_lock is only allowed for type=workbook".format(path)
        raise ValueError(msg)


def _parse_overrides_outputs_container(raw: object, *, path: str) -> OutputContainerConfig:
    typed = _require_dict(raw, path=path)
    typ = _parse_overrides_outputs_container_type(typed, path=path)
    path_value: Any = _parse_overrides_outputs_container_path(typed.get("path"), container_type=typ, path=path)

    sheet_raw = typed.get("sheet")
    sheet = str(sheet_raw).strip() if isinstance(sheet_raw, str) else ""
    sheet = sheet or None

    encoding_raw = typed.get("encoding")
    encoding = str(encoding_raw).strip() if isinstance(encoding_raw, str) else ""
    encoding = encoding or DEFAULT_OUTPUT_ENCODING

    streaming = bool(typed.get("streaming", DEFAULT_OUTPUT_STREAMING))
    include_header = bool(typed.get("include_header", DEFAULT_OUTPUT_INCLUDE_HEADER))

    header_by = _parse_overrides_outputs_container_header_by(typed.get("header_fields_output_by"), path=path)

    allow_formulas = bool(typed.get("allow_formulas", False))
    write_lock = bool(typed.get("write_lock", False))

    _validate_overrides_outputs_container_semantics(
        typ,
        path=path,
        sheet=sheet,
        streaming=streaming,
        allow_formulas=allow_formulas,
        write_lock=write_lock,
    )

    return OutputContainerConfig(
        type=typ,
        path=path_value,
        sheet=sheet,
        encoding=encoding,
        streaming=streaming,
        include_header=include_header,
        header_fields_output_by=header_by,
        allow_formulas=allow_formulas,
        write_lock=write_lock,
    )


def _validate_overrides_output_keys(typed: Dict[str, Any], *, idx: int, path: str) -> None:
    extra_keys = sorted([str(k) for k in typed if str(k) not in _OVERRIDES_OUTPUT_ALLOWED_KEYS])
    if not extra_keys:
        return
    forbidden = sorted([k for k in extra_keys if k in _OVERRIDES_OUTPUT_FORBIDDEN_KEYS])
    unsupported = forbidden or extra_keys
    msg = "{}.{} has unsupported keys: {} (only supports: name/container/fields)".format(path, idx, ", ".join(unsupported))
    raise ValueError(msg)


def _parse_overrides_output_name(typed: Dict[str, Any], *, idx: int, path: str, seen_names: Set[str]) -> str:
    name = str(typed.get("name") or "").strip()
    if not name:
        msg = "{}.{}.name is required".format(path, idx)
        raise ValueError(msg)
    if not _OUTPUT_NAME_PATTERN.match(name):
        msg = "{}.{}.name={!r} is invalid; expected identifier like [a-zA-Z_][a-zA-Z0-9_]*".format(path, idx, name)
        raise ValueError(msg)
    if name in seen_names:
        msg = "{} has duplicate output name: {}".format(path, name)
        raise ValueError(msg)
    seen_names.add(name)
    return name


def _parse_overrides_output_fields(typed: Dict[str, Any], *, idx: int, path: str, known_field_ids: Set[str]) -> Tuple[str, ...]:
    fields_raw: object = typed.get("fields")
    if not _is_list(fields_raw):
        msg = "{}.{}.fields must be a list".format(path, idx)
        raise TypeError(msg)
    fields_list = fields_raw
    if not fields_list:
        msg = "{}.{}.fields must not be empty".format(path, idx)
        raise ValueError(msg)

    field_ids: List[str] = []
    for field_idx, field_id_raw in enumerate(fields_list):
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

    return tuple(field_ids)


def _parse_overrides_outputs_targets(
    raw: object,
    demand_ir: DemandIr,
    *,
    path: str,
) -> Tuple[OutputTargetConfig, ...]:
    if not _is_list(raw):
        msg = "{} must be a list".format(path)
        raise TypeError(msg)
    outputs = raw
    if not outputs:
        msg = "{} cannot be empty".format(path)
        raise ValueError(msg)

    known_field_ids: Set[str] = {str(fid) for fid in demand_ir.fields}
    seen_names: Set[str] = set()
    parsed: List[OutputTargetConfig] = []

    for idx, item in enumerate(outputs):
        if not isinstance(item, dict):
            msg = "{}.{} must be an object".format(path, idx)
            raise TypeError(msg)
        typed = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing

        _validate_overrides_output_keys(typed, idx=idx, path=path)
        name = _parse_overrides_output_name(typed, idx=idx, path=path, seen_names=seen_names)
        container = _parse_overrides_outputs_container(typed.get("container"), path="{}.{}.container".format(path, idx))
        field_ids = _parse_overrides_output_fields(typed, idx=idx, path=path, known_field_ids=known_field_ids)

        parsed.append(
            OutputTargetConfig(
                name=name,
                from_=None,
                container=container,
                fields=field_ids,
                where=None,
                aggregate=None,
                requires=(),
            )
        )

    return tuple(parsed)


def _should_validate_unique_effective_field_display_names(config: DemandConfig, outputs: Tuple[OutputTargetConfig, ...]) -> bool:
    if not bool(config.validate_unique_field_names):
        return False
    for t in outputs:
        container = t.container
        if container is None:
            continue
        if container.include_header and str(container.header_fields_output_by) == "name":
            return True
    return False


def _validate_unique_effective_field_display_names(demand_ir: DemandIr) -> None:
    conflicts: Dict[str, List[str]] = {}
    for field_id, field_ir in demand_ir.fields.items():
        name = str(field_ir.name or "").strip()
        effective = name or str(field_id)
        conflicts.setdefault(effective, []).append(str(field_id))

    duplicates = {name: ids for name, ids in conflicts.items() if len(ids) > 1}
    if not duplicates:
        return

    parts: List[str] = []
    for name in sorted(duplicates.keys()):
        parts.append("{!r}: {}".format(name, ", ".join(sorted(duplicates[name]))))
    conflicts_str = "; ".join(parts)
    msg = "".join(
        [
            "Duplicate effective field display names detected (validate_unique_field_names=true). ",
            "This is not allowed when outputs include header_fields_output_by=name and include_header=true. ",
            "Conflicts: {}".format(conflicts_str),
        ]
    )
    raise ValueError(msg)


def _as_guardrail_mode(value: str) -> GuardrailMode:
    if value == "quiet":
        return "quiet"
    if value == "fast_fail":
        return "fast_fail"
    msg = "Invalid guardrail mode: '{}'".format(value)
    raise ValueError(msg)


def _compile_guardrails_policy(config: Optional[GuardrailsConfig]) -> GuardrailsPolicy:
    if config is None:
        return GuardrailsPolicy.disabled()

    loader = config.loader
    relations = config.relations
    compute = config.compute

    return GuardrailsPolicy(
        enabled=bool(config.enabled),
        mode=_as_guardrail_mode(str(config.mode)),
        loader=GuardrailsLoaderPolicy(
            validate_result=bool(loader.validate_result) if loader is not None else False,
            required_fields=tuple(str(item) for item in (loader.required_fields or ())) if loader is not None else (),
            on_transform_error=_as_guardrail_mode(str(loader.on_transform_error))
            if (loader is not None and loader.on_transform_error)
            else None,
        ),
        relations=GuardrailsRelationsPolicy(
            null_key_max_rate=relations.null_key_max_rate if relations is not None else None,
            type_error_max_rate=relations.type_error_max_rate if relations is not None else None,
        ),
        compute=GuardrailsComputePolicy(
            on_error=_as_guardrail_mode(str(compute.on_error)) if (compute is not None and compute.on_error) else None,
        ),
    )


def _retry_spec_from_yaml(
    config: Optional[LoaderRetryConfig],
    *,
    resolver: SecurePythonReferenceResolver,
) -> LoaderRetryPolicySpec:
    if config is None:
        return LoaderRetryPolicySpec()
    should_retry = None
    if config.should_retry:
        should_retry = cast("Any", resolver.resolve(str(config.should_retry)))  # pragma: allow-cast resolver callable signature boundary
    return LoaderRetryPolicySpec(
        enabled=bool(config.enabled) if config.enabled is not None else None,
        should_retry=should_retry,
        max_attempts=int(config.max_attempts) if config.max_attempts is not None else None,
        max_elapsed_seconds=float(config.max_elapsed_seconds) if config.max_elapsed_seconds is not None else None,
        backoff=str(config.backoff) if config.backoff is not None else None,
        base_delay_seconds=float(config.base_delay_seconds) if config.base_delay_seconds is not None else None,
        max_delay_seconds=float(config.max_delay_seconds) if config.max_delay_seconds is not None else None,
        jitter=bool(config.jitter) if config.jitter is not None else None,
    )


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


def _finalize_retry_policy(spec: LoaderRetryPolicySpec, *, base: Optional[LoaderRetryPolicy] = None) -> LoaderRetryPolicy:
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
        msg = "loader_retry.enabled=true requires should_retry (provide in YAML or via driver injection)"
        raise ValueError(msg)

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
    resolver: SecurePythonReferenceResolver,
    overrides: Optional[LoaderRetryPoliciesSpec],
) -> Optional[LoaderRetryPolicies]:
    yaml_global = _retry_spec_from_yaml(config.retry, resolver=resolver)
    driver_global = overrides.default if overrides is not None else None
    global_spec = _merge_retry_specs(yaml_global, driver_global)

    base_policy = LoaderRetryPolicy.disabled()
    global_policy = _finalize_retry_policy(global_spec, base=base_policy)

    known_loaders = set(config.sources.keys())
    known_loaders.add(config.main_source.source_id)
    if overrides is not None and overrides.by_loader:
        unknown = set(overrides.by_loader.keys()) - known_loaders
        if unknown:
            msg = "Unknown loader_retry.by_loader keys: {}".format(", ".join(sorted(unknown)))
            raise ValueError(msg)

    by_loader: Dict[str, LoaderRetryPolicy] = {}

    main_source_id = config.main_source.source_id
    main_yaml = _retry_spec_from_yaml(config.main_source.retry, resolver=resolver)
    main_driver = overrides.by_loader.get(main_source_id) if overrides is not None else None
    main_spec = _merge_retry_specs(_merge_retry_specs(global_spec, main_yaml), main_driver)
    main_policy = _finalize_retry_policy(main_spec, base=base_policy)
    if main_policy != global_policy:
        by_loader[main_source_id] = main_policy

    for source_id, source_config in config.sources.items():
        src_yaml = _retry_spec_from_yaml(source_config.retry, resolver=resolver)
        src_driver = overrides.by_loader.get(source_id) if overrides is not None else None
        src_spec = _merge_retry_specs(_merge_retry_specs(global_spec, src_yaml), src_driver)
        src_policy = _finalize_retry_policy(src_spec, base=base_policy)
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
    allowed_yaml_roots: Optional[Sequence[str]] = None,
) -> DemandConfig:
    loader = YamlDemandLoader()
    return loader.load(
        yaml_path,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
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
    resolver: SecurePythonReferenceResolver,
    init_vars: Optional[Dict[str, object]] = None,
) -> DemandIr:
    converter = ConfigToIRConverter(resolver=resolver, init_vars=init_vars)
    return converter.convert(config)


def _resolve_effective_outputs_and_path(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    options: RunOptions,
) -> Tuple[Tuple[OutputTargetConfig, ...], str]:
    overrides_outputs = options.overrides.outputs if options.overrides is not None else None
    if overrides_outputs is not None:
        return _parse_overrides_outputs_targets(overrides_outputs, demand_ir, path="overrides.outputs"), "overrides.outputs"
    if config.outputs:
        return tuple(config.outputs), "outputs"
    return (), "outputs"


def _compile_output_composition_for_outputs(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    effective_outputs: Tuple[OutputTargetConfig, ...],
    outputs_path: str,
    options: RunOptions,
    resolver: SecurePythonReferenceResolver,
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
            resolver=resolver,
            init_vars=options.init_vars,
            workflow_managed_output_ids=options.workflow_managed_output_ids,
            outputs_path=outputs_path,
            skip_extra_sheets_without_workbook=options.overrides is not None and options.overrides.outputs is not None,
        ),
    )


def build_request(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    options: RunOptions,
    resolver: SecurePythonReferenceResolver,
) -> ExecutionRequest:
    effective_outputs, outputs_path = _resolve_effective_outputs_and_path(config, demand_ir, options=options)
    output_composition = _compile_output_composition_for_outputs(
        config,
        demand_ir,
        effective_outputs=effective_outputs,
        outputs_path=outputs_path,
        options=options,
        resolver=resolver,
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
    components = list(options.components or [])
    if config.observability is not None:
        observability, observers = compile_observability_spec(config.observability)
        components.extend(observers)

    if options.overrides is not None:
        viz_config = options.overrides.viz_config
        if not isinstance(viz_config, UnsetType):
            viz_override = viz_config
            if viz_override is None:
                if observability is not None:
                    observability = replace(observability, viz_config=None)
            elif observability is None:
                observability = ObservabilitySpec(viz_config=viz_override)
            else:
                observability = replace(observability, viz_config=viz_override)
    if not components:
        components = None

    guardrails = options.guardrails or _compile_guardrails_policy(config.guardrails)
    loader_retry = _compile_loader_retry_policies(config, resolver=resolver, overrides=options.loader_retry)
    batch_size = options.batch_size if options.batch_size is not None else config.batch_size

    return ExecutionRequest(
        export_layout=export_layout,
        output=output_spec,
        sink=options.sink,
        output_composition=output_composition,
        observability=observability,
        guardrails=guardrails,
        loader_retry=loader_retry,
        components=components,
        batch_size=batch_size,
        parallel_mode=options.parallel_mode,
        max_workers=options.max_workers,
        key_normalization=options.key_normalization,
    )


def compile(  # noqa: A001
    yaml_path: str,
    *,
    options: RunOptions,
) -> Compilation:
    validate_allowlist(allowed_modules=options.allowed_modules, allowed_functions=options.allowed_functions)
    config = load_config(
        yaml_path,
        template_vars=options.template_vars,
        template_sandbox=options.template_sandbox,
        allowed_yaml_roots=options.allowed_yaml_roots,
    )
    base_module_path = None
    if _config_uses_relative_references(config):
        base_module_path = derive_base_module_path(yaml_path)
    resolver = create_reference_resolver(
        allowed_modules=options.allowed_modules,
        allowed_functions=options.allowed_functions,
        resolver_trusted_mode=options.resolver_trusted_mode,
        base_module_path=base_module_path,
        builtin_callables=options.builtin_callables,
        public_builtin_callable_ids=options.public_builtin_callable_ids,
    )
    demand_ir = compile_ir(config, resolver=resolver, init_vars=options.init_vars)
    request = build_request(config, demand_ir, options=options, resolver=resolver)
    return Compilation(
        config=config,
        demand_ir=demand_ir,
        request=request,
    )


__all__ = [
    "build_request",
    "compile",
    "compile_ir",
    "create_reference_resolver",
    "load_config",
    "validate_allowlist",
]


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
