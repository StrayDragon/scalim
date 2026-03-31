"""`YAML DSL` 运行时编译器.

本模块将 `YAML DSL` 文件转换为:
- 已校验的配置(`DemandConfig`)
- 中间表示(`DemandIr`)
- 运行时请求(`ExecutionRequest`)
"""

import os
import re
from pathlib import Path
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
from ....spec.ir import DemandIr
from ....vendor.compact.typing_extensionsx import TypeGuard
from ....vendor.dataclassesx import replace
from ..config_parsing.loader import YamlDemandLoader
from ..config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from ..init_var_nodes import parse_init_var_mapping_node
from ..reference_syntax import BUILTIN_CALLABLE_REFERENCE_PREFIX
from ..schema_dsl.constants import (
    DEFAULT_OUTPUT_ENCODING,
    DEFAULT_OUTPUT_HEADER_BY,
    DEFAULT_OUTPUT_INCLUDE_HEADER,
    DEFAULT_OUTPUT_STREAMING,
)
from ..schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    GuardrailsConfig,
    LoaderRetryConfig,
    OutputContainerConfig,
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
)
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
_OVERRIDES_OUTPUT_ALLOWED_KEYS: FrozenSet[str] = frozenset(["name", "container", "to", "write", "fields"])
_OVERRIDES_OUTPUT_FORBIDDEN_KEYS: FrozenSet[str] = frozenset(["where", "from", "aggregate"])
_OUTPUT_CONTAINER_TYPES: Tuple[str, ...] = ("csv",)
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


def _parse_overrides_outputs_container_path(path_raw: Any, *, path: str) -> Any:
    if isinstance(path_raw, dict):
        return {
            "$init_var": parse_init_var_mapping_node(
                cast("Dict[str, Any]", path_raw),  # pragma: allow-cast yaml mapping typed narrowing
                path="{}.path".format(path),
            )
        }
    if path_raw is None:
        msg = "{}.path is required".format(path)
        raise ValueError(msg)
    if isinstance(path_raw, os.PathLike):
        value = str(os.fspath(path_raw)).strip()
        if not value:
            msg = "{}.path is required".format(path)
            raise ValueError(msg)
        return value
    if isinstance(path_raw, str):
        value = path_raw.strip()
        if not value:
            msg = "{}.path is required".format(path)
            raise ValueError(msg)
        return value
    msg = "{}.path must be a non-empty string or {{$init_var: <name>}}".format(path)
    raise TypeError(msg)


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
    streaming: bool,
) -> None:
    if container_type != "csv":
        msg = "{}.type={!r} is invalid; expected one of: {}".format(path, container_type, ", ".join(_OUTPUT_CONTAINER_TYPES))
        raise ValueError(msg)
    if not streaming:
        msg = "{}.streaming must be true (composed outputs only support streaming=true)".format(path)
        raise ValueError(msg)


def _parse_overrides_outputs_container(raw: object, *, path: str) -> OutputContainerConfig:
    typed = _require_dict(raw, path=path)
    allowed_keys = {"type", "path", "encoding", "streaming", "include_header", "header_fields_output_by"}
    unknown = sorted({str(k) for k in typed} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ValueError(msg)
    typ = _parse_overrides_outputs_container_type(typed, path=path)
    path_value: Any = _parse_overrides_outputs_container_path(typed.get("path"), path=path)

    encoding_raw = typed.get("encoding")
    encoding = str(encoding_raw).strip() if isinstance(encoding_raw, str) else ""
    encoding = encoding or DEFAULT_OUTPUT_ENCODING

    streaming = bool(typed.get("streaming", DEFAULT_OUTPUT_STREAMING))
    include_header = bool(typed.get("include_header", DEFAULT_OUTPUT_INCLUDE_HEADER))

    header_by = _parse_overrides_outputs_container_header_by(typed.get("header_fields_output_by"), path=path)

    _validate_overrides_outputs_container_semantics(
        typ,
        path=path,
        streaming=streaming,
    )

    return OutputContainerConfig(
        type=typ,
        path=path_value,
        encoding=encoding,
        streaming=streaming,
        include_header=include_header,
        header_fields_output_by=header_by,
    )


def _parse_overrides_output_to(raw: object, *, path: str) -> Optional[OutputToConfig]:
    if raw is None:
        return None
    typed = _require_dict(raw, path=path)
    allowed_keys = {"book", "sheet"}
    unknown = sorted({str(k) for k in typed} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ValueError(msg)

    book_raw = typed.get("book")
    sheet_raw = typed.get("sheet")

    book = None
    if book_raw is not None:
        if not isinstance(book_raw, str):
            msg = "{}.book must be a string".format(path)
            raise TypeError(msg)
        book = str(book_raw).strip() or None

    sheet = None
    if sheet_raw is not None:
        if not isinstance(sheet_raw, str):
            msg = "{}.sheet must be a string".format(path)
            raise TypeError(msg)
        sheet = str(sheet_raw).strip() or None

    if book is None and sheet is None:
        return None
    return OutputToConfig(book=book, sheet=sheet)


def _parse_overrides_output_write(raw: object, *, path: str) -> Optional[OutputWriteConfig]:
    if raw is None:
        return None
    typed = _require_dict(raw, path=path)
    allowed_keys = {"mode", "align_by", "header_policy", "on_mismatch", "on_conflict"}
    unknown = sorted({str(k) for k in typed} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ValueError(msg)

    def _as_opt_str(key: str) -> Optional[str]:
        value = typed.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            msg = "{}.{} must be a string".format(path, key)
            raise TypeError(msg)
        raw_str = str(value).strip()
        return raw_str or None

    return OutputWriteConfig(
        mode=_as_opt_str("mode"),
        align_by=_as_opt_str("align_by"),
        header_policy=_as_opt_str("header_policy"),
        on_mismatch=_as_opt_str("on_mismatch"),
        on_conflict=_as_opt_str("on_conflict"),
    )


def _validate_overrides_output_keys(typed: Dict[str, Any], *, idx: int, path: str) -> None:
    extra_keys = sorted([str(k) for k in typed if str(k) not in _OVERRIDES_OUTPUT_ALLOWED_KEYS])
    if not extra_keys:
        return
    forbidden = sorted([k for k in extra_keys if k in _OVERRIDES_OUTPUT_FORBIDDEN_KEYS])
    unsupported = forbidden or extra_keys
    msg = "{}.{} has unsupported keys: {} (only supports: name/to/write/container/fields)".format(path, idx, ", ".join(unsupported))
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
        container_raw = typed.get("container")
        container = (
            None if container_raw is None else _parse_overrides_outputs_container(container_raw, path="{}.{}.container".format(path, idx))
        )
        to_cfg = _parse_overrides_output_to(typed.get("to"), path="{}.{}.to".format(path, idx))
        write_cfg = _parse_overrides_output_write(typed.get("write"), path="{}.{}.write".format(path, idx))
        field_ids = _parse_overrides_output_fields(typed, idx=idx, path=path, known_field_ids=known_field_ids)

        if container is not None and to_cfg is not None:
            msg = "{}.{} cannot declare both container and to".format(path, idx)
            raise ValueError(msg)
        if container is not None and write_cfg is not None:
            msg = "{}.{} cannot declare write for csv container outputs".format(path, idx)
            raise ValueError(msg)

        parsed.append(
            OutputTargetConfig(
                name=name,
                from_=None,
                container=container,
                to=to_cfg,
                write=write_cfg,
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


def _parse_non_empty_path_or_init_var(raw: object, *, path: str) -> Any:
    if isinstance(raw, dict):
        return {"$init_var": parse_init_var_mapping_node(cast("Dict[str, Any]", raw), path=path)}  # pragma: allow-cast dict narrowing
    if raw is None:
        msg = "{} is required".format(path)
        raise ValueError(msg)
    if isinstance(raw, os.PathLike):
        value = str(os.fspath(raw)).strip()
        if not value:
            msg = "{} is required".format(path)
            raise ValueError(msg)
        return value
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            msg = "{} is required".format(path)
            raise ValueError(msg)
        return value
    msg = "{} must be a non-empty string or {{$init_var: <name>}}".format(path)
    raise TypeError(msg)


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


def _overlay_optional_str_field(patch: Mapping[str, object], *, key: str, value: str, path: str) -> str:
    if key not in patch:
        return value
    raw = patch.get(key)
    if raw is None:
        return value
    if not isinstance(raw, str):
        msg = "{}.{} must be a string".format(path, str(key))
        raise TypeError(msg)
    return str(raw).strip()


def _overlay_book_write_defaults(base: BookWriteDefaultsConfig, patch: Mapping[str, object], *, path: str) -> BookWriteDefaultsConfig:
    allowed_keys = {"mode", "align_by", "header_policy", "on_mismatch", "on_conflict"}
    unknown = sorted({str(k) for k in patch} - allowed_keys)
    if unknown:
        msg = "{} contains unknown keys: {}".format(path, ", ".join(unknown))
        raise ValueError(msg)

    mode = str(base.mode or DEFAULT_BOOK_WRITE_MODE)
    align_by = str(base.align_by or DEFAULT_BOOK_WRITE_ALIGN_BY)
    header_policy = str(base.header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY)
    on_mismatch = str(base.on_mismatch or DEFAULT_BOOK_WRITE_ON_MISMATCH)
    on_conflict = str(base.on_conflict or DEFAULT_BOOK_WRITE_ON_CONFLICT)

    mode = _overlay_optional_str_field(patch, key="mode", value=mode, path=path)
    align_by = _overlay_optional_str_field(patch, key="align_by", value=align_by, path=path)
    header_policy = _overlay_optional_str_field(patch, key="header_policy", value=header_policy, path=path)
    on_mismatch = _overlay_optional_str_field(patch, key="on_mismatch", value=on_mismatch, path=path)
    on_conflict = _overlay_optional_str_field(patch, key="on_conflict", value=on_conflict, path=path)

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


def _apply_book_patch(base: Optional[BookConfig], patch: Mapping[str, object], *, path: str) -> BookConfig:  # noqa: C901, PLR0912, PLR0915
    allowed_keys = {"kind", "path", "budget", "export_xlsx", "allow_formulas", "write_lock", "write_defaults"}
    unknown = sorted({str(k) for k in patch} - allowed_keys)
    if unknown:
        msg = "{} contains unknown keys: {}".format(path, ", ".join(unknown))
        raise ValueError(msg)

    kind = str(base.kind or "").strip() if base is not None else ""
    book_path: Any = base.path if base is not None else None
    budget = base.budget if base is not None else None
    export_xlsx = base.export_xlsx if base is not None else None
    allow_formulas = bool(base.allow_formulas) if base is not None else False
    write_lock = bool(base.write_lock) if base is not None else False
    write_defaults = base.write_defaults if base is not None else None

    has_path_key = "path" in patch
    has_allow_formulas_key = "allow_formulas" in patch
    has_write_lock_key = "write_lock" in patch
    has_budget_key = "budget" in patch
    has_export_key = "export_xlsx" in patch

    if "kind" in patch:
        raw = patch.get("kind")
        kind = str(raw or "").strip() if isinstance(raw, str) else ""
        if not kind:
            msg = "{}.kind must be a non-empty string".format(path)
            raise ValueError(msg)

    if has_path_key:
        book_path = _parse_optional_path_or_init_var(patch.get("path"), path="{}.path".format(path))

    if has_allow_formulas_key:
        raw = patch.get("allow_formulas")
        if not isinstance(raw, bool):
            msg = "{}.allow_formulas must be a bool".format(path)
            raise TypeError(msg)
        allow_formulas = bool(raw)

    if has_write_lock_key:
        raw = patch.get("write_lock")
        if not isinstance(raw, bool):
            msg = "{}.write_lock must be a bool".format(path)
            raise TypeError(msg)
        write_lock = bool(raw)

    if has_budget_key:
        raw = patch.get("budget")
        if raw is None:
            budget = None
        elif not isinstance(raw, dict):
            msg = "{}.budget must be a mapping".format(path)
            raise TypeError(msg)
        else:
            raw_dict = cast("Dict[str, Any]", raw)  # pragma: allow-cast runtime dict typed narrowing
            max_sheets_raw = raw_dict.get("max_sheets")
            max_total_cells_raw = raw_dict.get("max_total_cells")
            if budget is None:
                if max_sheets_raw is None or max_total_cells_raw is None:
                    msg = "{}.budget requires max_sheets and max_total_cells when creating a new xlsx_memory book".format(path)
                    raise ValueError(msg)
                try:
                    max_sheets = int(max_sheets_raw)
                except (TypeError, ValueError):
                    msg = "{}.budget.max_sheets must be an integer >= 1".format(path)
                    raise ValueError(msg) from None
                try:
                    max_total_cells = int(max_total_cells_raw)
                except (TypeError, ValueError):
                    msg = "{}.budget.max_total_cells must be an integer >= 1".format(path)
                    raise ValueError(msg) from None
                if int(max_sheets) < 1:
                    msg = "{}.budget.max_sheets must be >= 1".format(path)
                    raise ValueError(msg)
                if int(max_total_cells) < 1:
                    msg = "{}.budget.max_total_cells must be >= 1".format(path)
                    raise ValueError(msg)
                budget = BookBudgetConfig(max_sheets=int(max_sheets), max_total_cells=int(max_total_cells))
            else:
                max_sheets = int(budget.max_sheets)
                max_total_cells = int(budget.max_total_cells)
                if max_sheets_raw is not None:
                    try:
                        max_sheets = int(max_sheets_raw)
                    except (TypeError, ValueError):
                        msg = "{}.budget.max_sheets must be an integer >= 1".format(path)
                        raise ValueError(msg) from None
                if max_total_cells_raw is not None:
                    try:
                        max_total_cells = int(max_total_cells_raw)
                    except (TypeError, ValueError):
                        msg = "{}.budget.max_total_cells must be an integer >= 1".format(path)
                        raise ValueError(msg) from None
                if int(max_sheets) < 1:
                    msg = "{}.budget.max_sheets must be >= 1".format(path)
                    raise ValueError(msg)
                if int(max_total_cells) < 1:
                    msg = "{}.budget.max_total_cells must be >= 1".format(path)
                    raise ValueError(msg)
                budget = BookBudgetConfig(max_sheets=int(max_sheets), max_total_cells=int(max_total_cells))

    if has_export_key:
        raw = patch.get("export_xlsx")
        if raw is None:
            export_xlsx = None
        elif not isinstance(raw, dict):
            msg = "{}.export_xlsx must be a mapping".format(path)
            raise TypeError(msg)
        else:
            raw_dict = cast("Dict[str, Any]", raw)  # pragma: allow-cast runtime dict typed narrowing
            path_raw = raw_dict.get("path")
            write_lock_raw = raw_dict.get("write_lock")
            allow_formulas_raw = raw_dict.get("allow_formulas")
            if write_lock_raw is not None and not isinstance(write_lock_raw, bool):
                msg = "{}.export_xlsx.write_lock must be a bool".format(path)
                raise TypeError(msg)
            if allow_formulas_raw is not None and not isinstance(allow_formulas_raw, bool):
                msg = "{}.export_xlsx.allow_formulas must be a bool".format(path)
                raise TypeError(msg)
            if export_xlsx is None:
                if path_raw is None:
                    msg = "{}.export_xlsx.path is required when creating export_xlsx".format(path)
                    raise ValueError(msg)
                export_xlsx = BookExportXlsxConfig(
                    path=_parse_non_empty_path_or_init_var(path_raw, path="{}.export_xlsx.path".format(path)),
                    write_lock=bool(write_lock_raw) if write_lock_raw is not None else False,
                    allow_formulas=bool(allow_formulas_raw) if allow_formulas_raw is not None else False,
                )
            else:
                next_path = (
                    export_xlsx.path
                    if path_raw is None
                    else _parse_non_empty_path_or_init_var(path_raw, path="{}.export_xlsx.path".format(path))
                )
                next_write_lock = export_xlsx.write_lock if write_lock_raw is None else bool(write_lock_raw)
                next_allow_formulas = export_xlsx.allow_formulas if allow_formulas_raw is None else bool(allow_formulas_raw)
                export_xlsx = BookExportXlsxConfig(
                    path=next_path,
                    write_lock=bool(next_write_lock),
                    allow_formulas=bool(next_allow_formulas),
                )

    if "write_defaults" in patch:
        raw = patch.get("write_defaults")
        if raw is None:
            write_defaults = None
        elif not isinstance(raw, dict):
            msg = "{}.write_defaults must be a mapping".format(path)
            raise TypeError(msg)
        else:
            raw_dict = cast("Dict[str, Any]", raw)  # pragma: allow-cast runtime dict typed narrowing
            base_defaults = write_defaults
            if base_defaults is None:
                base_defaults = BookWriteDefaultsConfig(
                    mode=str(DEFAULT_BOOK_WRITE_MODE),
                    align_by=str(DEFAULT_BOOK_WRITE_ALIGN_BY),
                    header_policy=str(DEFAULT_BOOK_WRITE_HEADER_POLICY),
                    on_mismatch=str(DEFAULT_BOOK_WRITE_ON_MISMATCH),
                    on_conflict=str(DEFAULT_BOOK_WRITE_ON_CONFLICT),
                )
            write_defaults = _overlay_book_write_defaults(base_defaults, raw_dict, path="{}.write_defaults".format(path))

    if kind not in BOOK_KINDS:
        msg = "{}.kind={!r} is invalid; expected one of: {}".format(path, kind, ", ".join(BOOK_KINDS))
        raise ValueError(msg)

    if kind == "xlsx_file":
        if has_budget_key or has_export_key:
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
        if has_path_key or has_allow_formulas_key or has_write_lock_key:
            msg = "{}.path/allow_formulas/write_lock are not allowed for kind=xlsx_memory (use export_xlsx.*)".format(path)
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
        if write_lock:
            msg = "{}.write_lock is not allowed for kind=xlsx_memory".format(path)
            raise ValueError(msg)

    return BookConfig(
        kind=str(kind),
        path=book_path,
        budget=budget,
        export_xlsx=export_xlsx,
        allow_formulas=bool(allow_formulas),
        write_lock=bool(write_lock),
        write_defaults=write_defaults,
    )


def _apply_resources_io_override(config: DemandConfig, patch_raw: object) -> DemandConfig:
    if not isinstance(patch_raw, dict):
        msg = "overrides.resources must be an object"
        raise TypeError(msg)
    patch = cast("Dict[str, Any]", patch_raw)  # pragma: allow-cast runtime dict typed narrowing
    unknown = sorted({str(k) for k in patch} - {"books"})
    if unknown:
        msg = "overrides.resources has unknown keys: {}".format(", ".join(unknown))
        raise ValueError(msg)

    books_obj = patch.get("books")
    if books_obj is None:
        return config
    if not isinstance(books_obj, dict):
        msg = "overrides.resources.books must be an object"
        raise TypeError(msg)
    books_patch = cast("Dict[str, Any]", books_obj)  # pragma: allow-cast runtime dict typed narrowing
    base_resources = config.resources
    merged_books: Dict[str, BookConfig] = dict(base_resources.books) if base_resources is not None else {}

    for raw_book_id, raw_book_patch in books_patch.items():
        if not isinstance(raw_book_id, str) or not str(raw_book_id).strip():
            msg = "overrides.resources.books keys must be non-empty strings"
            raise ValueError(msg)
        book_id = str(raw_book_id).strip()
        if not isinstance(raw_book_patch, dict):
            msg = "overrides.resources.books.{} must be an object".format(book_id)
            raise TypeError(msg)
        base_book = merged_books.get(book_id)
        merged_books[book_id] = _apply_book_patch(
            base_book,
            cast("Mapping[str, object]", raw_book_patch),  # pragma: allow-cast runtime dict typed narrowing
            path="overrides.resources.books.{}".format(book_id),
        )

    return replace(config, resources=ResourcesConfig(books=merged_books))


def _apply_io_overrides(config: DemandConfig, *, options: RunOptions) -> DemandConfig:
    overrides = options.overrides
    if overrides is None:
        return config

    next_config = config

    resources_patch = overrides.resources
    if resources_patch is not None:
        next_config = _apply_resources_io_override(next_config, resources_patch)

    return next_config


def _compile_output_composition_for_outputs(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    effective_outputs: Tuple[OutputTargetConfig, ...],
    outputs_path: str,
    yaml_base_dir: str,
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
            yaml_base_dir=str(yaml_base_dir),
            workflow_managed_output_ids=options.workflow_managed_output_ids,
            outputs_path=outputs_path,
            skip_extra_sheets_without_workbook=options.overrides is not None and options.overrides.outputs is not None,
        ),
    )


def build_request(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    yaml_base_dir: str,
    options: RunOptions,
    resolver: SecurePythonReferenceResolver,
) -> ExecutionRequest:
    effective_config = _apply_io_overrides(config, options=options)
    effective_outputs, outputs_path = _resolve_effective_outputs_and_path(effective_config, demand_ir, options=options)
    output_composition = _compile_output_composition_for_outputs(
        effective_config,
        demand_ir,
        effective_outputs=effective_outputs,
        outputs_path=outputs_path,
        yaml_base_dir=str(yaml_base_dir),
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
    if effective_config.observability is not None:
        observability, observers = compile_observability_spec(effective_config.observability)
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

    guardrails = options.guardrails or _compile_guardrails_policy(effective_config.guardrails)
    loader_retry = _compile_loader_retry_policies(effective_config, resolver=resolver, overrides=options.loader_retry)
    batch_size = options.batch_size if options.batch_size is not None else effective_config.batch_size

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
        rendered_yaml_max_len=options.rendered_yaml_max_len,
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
    yaml_base_dir = str(Path(str(yaml_path)).expanduser().resolve(strict=False).parent)
    request = build_request(config, demand_ir, yaml_base_dir=yaml_base_dir, options=options, resolver=resolver)
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
