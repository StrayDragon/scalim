# pragma: allow-c901-file plan: c70
"""`YAML DSL` 运行时编译器.

本模块将 `YAML DSL` 文件转换为:
- 已校验的配置(`DemandConfig`)
- 中间表示(`DemandIr`)
- 运行时请求(`ExecutionRequest`)
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ....events import generate_run_id
from ....execution.guardrails import GuardrailsPolicy
from ....execution.loader_retry import LoaderRetryPolicies, LoaderRetryPoliciesSpec, LoaderRetryPolicy, LoaderRetryPolicySpec
from ....execution.run_ir import ExecutionRequest, ObservabilitySpec, OutputSpec, export_layout_from_demand_ir
from ....spec.ir import DemandIr
from ....typedefs import parse_failure_policy
from ....vendor.dataclassesx import replace
from .._internal import resource_override as _resource_override_ssot
from .._internal.config_parsing.loader import YamlDemandLoader
from .._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from ..book_resource_policy import ResourcesPolicy, materialize_resources_policy_onto_books
from ..diagnostics import format_duplicate_effective_field_display_names_message
from ..reference_syntax import BUILTIN_CALLABLE_REFERENCE_PREFIX
from ..schema_dsl.models import (
    DemandConfig,
    OutputTargetConfig,
)
from ._internal.callable_preflight import validate_signature_accepts_any_candidate
from .builtin_callables import parse_builtin_callable_id
from .contracts import (
    CaptureRows,
    Compilation,
    DemandRunOptions,
    OutputOverride,
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


def _parse_overrides_outputs_defaults_book_id(defaults: Optional[object], *, path: str) -> Optional[str]:
    return _resource_override_ssot.parse_outputs_defaults_book_id(defaults, path=str(path))


def _apply_default_book_binding_to_outputs(
    outputs: Tuple[OutputTargetConfig, ...],
    *,
    default_book_id: str,
) -> Tuple[OutputTargetConfig, ...]:
    return _resource_override_ssot.apply_default_book_binding_to_outputs(outputs, default_book_id=str(default_book_id))


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
        failure_policy = parse_failure_policy(options.runtime.demand_failure_policy, label="demand_failure_policy")
        next_config = replace(next_config, failure_policy=failure_policy)

    demand_diagnostics = options.runtime.demand_diagnostics
    if demand_diagnostics is not None:
        next_config = replace(
            next_config,
            include_full_error_message=bool(demand_diagnostics.include_full_error_message),
            validate_unique_field_names=bool(demand_diagnostics.validate_unique_field_names),
        )

    return next_config


def _apply_output_extras_overrides(config: DemandConfig, *, options: DemandRunOptions) -> DemandConfig:
    overrides = options.outputs.overrides
    if overrides is None or overrides.output_extras is None:
        return config
    meta, audit = _resource_override_ssot.compile_output_extras_override(
        overrides.output_extras,
        path="overrides.output_extras",
    )
    return replace(config, meta=meta, audit=audit)


def _parse_overrides_outputs_targets(
    overrides: Sequence[OutputOverride],
    demand_ir: DemandIr,
    *,
    path: str,
    default_book_id: Optional[str],
    default_book_ref: str,
) -> Tuple[OutputTargetConfig, ...]:
    known_field_ids: Set[str] = {str(fid) for fid in demand_ir.fields}
    return _resource_override_ssot.parse_overrides_outputs_targets(
        overrides,
        path=str(path),
        default_book_id=default_book_id,
        default_book_ref=str(default_book_ref),
        known_field_ids=known_field_ids,
    )


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


def _apply_resources_override(config: DemandConfig, override: ResourcesOverride) -> DemandConfig:
    return _resource_override_ssot.overlay_resources_override(config, override, path="overrides.resources")


def _apply_io_overrides(config: DemandConfig, *, options: DemandRunOptions) -> DemandConfig:
    overrides = options.outputs.overrides
    next_config = config

    if overrides is not None:
        resources_override = overrides.resources
        if resources_override is not None:
            next_config = _apply_resources_override(next_config, resources_override)

    policy = options.resources_policy if isinstance(options.resources_policy, ResourcesPolicy) else None
    return materialize_resources_policy_onto_books(next_config, policy)


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
        excel_column_residency=options.runtime.excel_column_residency,
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
