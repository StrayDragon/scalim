"""`YAML DSL` 运行时编译器.

本模块将 `YAML DSL` 文件转换为:
- 已校验的配置(`DemandConfig`)
- 中间表示(`DemandIr`)
- 运行时请求(`ExecutionRequest`)
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple, cast

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
from ....vendor.dataclassesx import replace
from ..config_parsing.loader import YamlDemandLoader
from ..reference_syntax import BUILTIN_CALLABLE_REFERENCE_PREFIX
from ..schema_dsl.models import DemandConfig, GuardrailsConfig, LoaderRetryConfig
from .builtin_callables import parse_builtin_callable_id
from .contracts import UNSET, Compilation, OutputOverrides, ResolverTrustedMode, RunOptions
from .conversion import ConfigToIRConverter
from .errors import ALLOWLIST_REQUIRED_MSG, AllowlistRequiredError, ResolverError
from .observability import compile_observability_spec
from .output_composition_yaml import compile_output_composition_from_yaml
from .references import SecurePythonReferenceResolver, derive_base_module_path

if TYPE_CHECKING:
    from ....ob.presets.viz import VizObserverConfig


def _ensure_allowlist(
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]],
) -> None:
    if not allowed_modules and not allowed_functions:
        # 安全审计:仅允许从 `allowlist` 中指定的模块/函数加载,避免 `YAML` 触发任意导入执行.
        raise AllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)


def validate_allowlist(
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]],
) -> None:
    _ensure_allowlist(allowed_modules, allowed_functions)


def _resolve_target_field_ids(
    demand_ir: DemandIr,
    overrides: Optional[OutputOverrides],
) -> List[str]:
    if overrides is not None and overrides.fields is not UNSET:
        raw_fields = cast("Optional[List[str]]", overrides.fields)
        if raw_fields is None:
            return list(demand_ir.fields.keys())
        if not raw_fields:
            msg = "overrides.output.fields cannot be empty (use None to select all fields)"
            raise ValueError(msg)
        return [str(fid) for fid in raw_fields]
    return list(demand_ir.fields.keys())


def _compile_output_spec(options: RunOptions) -> OutputSpec:
    spec = OutputSpec()

    overrides = options.overrides.output if options.overrides is not None else None
    if overrides is None:
        return spec

    if overrides.format is not UNSET:
        spec = replace(spec, format=str(overrides.format))
    if overrides.path is not UNSET:
        spec = replace(spec, path=overrides.path)
    if overrides.encoding is not UNSET:
        spec = replace(spec, encoding=str(overrides.encoding))
    if overrides.streaming is not UNSET:
        spec = replace(spec, streaming=bool(overrides.streaming))
    if overrides.include_header is not UNSET:
        spec = replace(spec, include_header=bool(overrides.include_header))

    return spec


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
        should_retry = cast("Any", resolver.resolve(str(config.should_retry)))
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
        should_retry=cast("Any", should_retry),
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
    except ResolverError as exc:
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
        return cast("Callable[..., Any]", value_raw)

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
        except ResolverError as exc:
            msg = "builtin_callables[{!r}]: failed to resolve Python reference {!r}: {}".format(builtin_id, reference, exc)
            raise ValueError(msg) from exc

    msg = "builtin_callables[{!r}]: expected a callable or Python reference string, got: {}".format(builtin_id, type(value_raw).__name__)
    raise TypeError(msg)


def _compile_builtin_callables_vocab(builtin_callables: Optional[Mapping[str, object]]) -> Optional[Dict[str, Callable[..., Any]]]:
    if builtin_callables is None:
        return None

    compiled: Dict[str, Callable[..., Any]] = {}
    trusted_resolver = SecurePythonReferenceResolver(
        allowed_modules=None,
        allowed_functions=None,
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
    compiled_builtin_callables = _compile_builtin_callables_vocab(builtin_callables)
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


def build_request(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    options: RunOptions,
    resolver: SecurePythonReferenceResolver,
) -> ExecutionRequest:
    output_overrides = options.overrides.output if options.overrides is not None else None
    yaml_output_composition = None
    if options.output_composition is None and config.outputs:
        yaml_output_composition = compile_output_composition_from_yaml(
            config,
            demand_ir,
            resolver=resolver,
            init_vars=options.init_vars,
            workflow_managed_output_ids=options.workflow_managed_output_ids,
        )
    output_composition = options.output_composition or yaml_output_composition

    # 单输出模式: 仍可通过 `overrides.output.*` 控制输出. 当启用 `outputs`/`output_composition` 时, `export_layout`/`output` 会被忽略.
    export_layout = export_layout_from_demand_ir(demand_ir, (), header_fields_output_by="field_id")
    output_spec = OutputSpec(path=None)
    if output_composition is None:
        target_field_ids = _resolve_target_field_ids(demand_ir, output_overrides)
        header_by = "field_id"
        if output_overrides is not None and output_overrides.header_fields_output_by is not UNSET:
            header_by = str(output_overrides.header_fields_output_by)
        export_layout = export_layout_from_demand_ir(
            demand_ir,
            target_field_ids,
            header_fields_output_by=header_by,
        )
        output_spec = _compile_output_spec(options)

    observability: Optional[ObservabilitySpec] = None
    components = list(options.components or [])
    if config.observability is not None:
        observability, observers = compile_observability_spec(config.observability)
        components.extend(observers)

    if options.overrides is not None and options.overrides.viz_config is not UNSET:
        viz_override = cast("Optional[VizObserverConfig]", options.overrides.viz_config)
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
