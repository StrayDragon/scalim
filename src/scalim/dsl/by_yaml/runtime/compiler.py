"""`YAML DSL` 运行时编译器.

本模块将 `YAML DSL` 文件转换为:
- 已校验的配置(`DemandConfig`)
- 中间表示(`DemandIr`)
- 运行时请求(`ExecutionRequest`)
"""

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional, cast

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
from ..config_parsing.loader import YamlDemandLoader
from ..schema_dsl.models import DemandConfig, GuardrailsConfig, LoaderRetryConfig
from .contracts import UNSET, Compilation, OutputOverrides, RunOptions
from .conversion import ConfigToIRConverter
from .errors import ALLOWLIST_REQUIRED_MSG, AllowlistRequiredError
from .observability import compile_observability_spec
from .references import SecurePythonReferenceResolver

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
    config: DemandConfig,
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
    if config.output and config.output.fields:
        return list(config.output.fields)
    return list(demand_ir.fields.keys())


def _compile_output_spec(config: DemandConfig, options: RunOptions) -> OutputSpec:
    spec = OutputSpec()
    if config.output:
        spec = OutputSpec(
            format=config.output.format,
            path=config.output.path,
            encoding=config.output.encoding,
            streaming=config.output.streaming,
            include_header=config.output.include_header,
        )

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


def load_config(yaml_path: str) -> DemandConfig:
    loader = YamlDemandLoader()
    return loader.load(yaml_path)


def create_reference_resolver(
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]],
) -> SecurePythonReferenceResolver:
    return SecurePythonReferenceResolver(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
    )


def compile_ir(
    config: DemandConfig,
    *,
    resolver: SecurePythonReferenceResolver,
) -> DemandIr:
    converter = ConfigToIRConverter(resolver=resolver)
    return converter.convert(config)


def build_request(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    options: RunOptions,
    resolver: SecurePythonReferenceResolver,
) -> ExecutionRequest:
    output_overrides = options.overrides.output if options.overrides is not None else None
    target_field_ids = _resolve_target_field_ids(config, demand_ir, output_overrides)

    header_by = config.output.header_fields_output_by if config.output else "field_id"
    if output_overrides is not None and output_overrides.header_fields_output_by is not UNSET:
        header_by = str(output_overrides.header_fields_output_by)

    export_layout = export_layout_from_demand_ir(
        demand_ir,
        target_field_ids,
        header_fields_output_by=header_by,
    )
    output_spec = _compile_output_spec(config, options)

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
        observability=observability,
        guardrails=guardrails,
        loader_retry=loader_retry,
        components=components,
        batch_size=batch_size,
        parallel_mode=options.parallel_mode,
        max_workers=options.max_workers,
    )


def compile(  # noqa: A001
    yaml_path: str,
    *,
    options: RunOptions,
) -> Compilation:
    validate_allowlist(allowed_modules=options.allowed_modules, allowed_functions=options.allowed_functions)
    config = load_config(yaml_path)
    resolver = create_reference_resolver(
        allowed_modules=options.allowed_modules,
        allowed_functions=options.allowed_functions,
    )
    demand_ir = compile_ir(config, resolver=resolver)
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
