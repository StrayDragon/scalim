from typing import Dict, FrozenSet, List, Mapping, Optional, Tuple, Union

from ....execution.guardrails import GuardrailsPolicy
from ....execution.key_normalization import normalize_key_normalization
from ....execution.loader_retry import LoaderRetryPoliciesSpec
from ....execution.run_ir import run_ir
from ....hooks import IExecutionHook
from ....ob.observer import Observer
from ....sinks import ISink
from ....typedefs import KeyNormalizationMode, ParallelMode
from .._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from .._public_template_sandbox import validate_public_template_sandbox
from .compiler import compile as _compile
from .contracts import UNSET, Compilation, DemandDiagnosticsPolicy, ResolverTrustedMode, RunOptions, RunOverrides, RunResult, UnsetType


def run(  # noqa: PLR0913
    yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    resolver_trusted_mode: ResolverTrustedMode = ResolverTrustedMode.STRICT_ALLOWLIST,
    components: Optional[List[Union[Observer, IExecutionHook]]] = None,
    sink: Optional[ISink] = None,
    overrides: Optional[RunOverrides] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    loader_retry: Optional[LoaderRetryPoliciesSpec] = None,
    batch_size: Union[Optional[int], UnsetType] = UNSET,
    demand_failure_policy: Optional[str] = None,
    demand_diagnostics: Optional[DemandDiagnosticsPolicy] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    key_normalization: KeyNormalizationMode = "raw",
    init_vars: Optional[Dict[str, object]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
    builtin_callables: Optional[Mapping[str, object]] = None,
    public_builtin_callable_ids: Optional[Tuple[str, ...]] = None,
) -> RunResult:
    """运行 `YAML DSL`,并支持显式覆盖项与输出 `sink`.

    优先级(高 -> 低):
    - `overrides.outputs`(完全覆盖 `YAML` 的 `outputs`; 整体替换,即 `replace`; 非空)
    - `YAML` 的 `outputs`(若声明)
    - 执行默认值

    注意:
    - YAML 主线不再支持 `observability.*`(旧字段会发出迁移告警并被忽略);可观测性通过 `components=[Observer()/Hook()]` 与
      `RunOverrides(viz_config=VizObserverConfig(...))` 装配.
    - `overrides.viz_config` 可启用/禁用 `viz` 并控制落盘路径、`trace` 输出与 `payload_policy` 策略等.
    - 当 `overrides.outputs` 把 `YAML` 中的 `workbook` 输出整体替换为非 `workbook` 输出时,未显式设置 `path` 的 `meta/audit`
      会被跳过;若仍需保留,请为 `meta.path` / `audit.path` 提供独立 `workbook` 路径.
    - 输出数据的保留完全由 `sink=...`(例如 `InMemoryRowSink`)决定,而不是由布尔开关控制.
    """
    template_sandbox = validate_public_template_sandbox(template_sandbox)
    options = RunOptions(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
        resolver_trusted_mode=resolver_trusted_mode,
        components=components,
        sink=sink,
        overrides=overrides,
        guardrails=guardrails,
        loader_retry=loader_retry,
        batch_size=batch_size,
        demand_failure_policy=demand_failure_policy,
        demand_diagnostics=demand_diagnostics,
        parallel_mode=parallel_mode,
        max_workers=max_workers,
        key_normalization=normalize_key_normalization(key_normalization),
        init_vars=init_vars,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
        builtin_callables=builtin_callables,
        public_builtin_callable_ids=public_builtin_callable_ids,
    )
    compilation = _compile(yaml_path, options=options)
    core = run_ir(compilation.demand_ir, compilation.request)
    return RunResult(core, config=compilation.config, yaml_path=yaml_path, sink=sink)


def compile(  # noqa: A001, PLR0913
    yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    resolver_trusted_mode: ResolverTrustedMode = ResolverTrustedMode.STRICT_ALLOWLIST,
    components: Optional[List[Union[Observer, IExecutionHook]]] = None,
    sink: Optional[ISink] = None,
    overrides: Optional[RunOverrides] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    loader_retry: Optional[LoaderRetryPoliciesSpec] = None,
    batch_size: Union[Optional[int], UnsetType] = UNSET,
    demand_failure_policy: Optional[str] = None,
    demand_diagnostics: Optional[DemandDiagnosticsPolicy] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    key_normalization: KeyNormalizationMode = "raw",
    init_vars: Optional[Dict[str, object]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
    builtin_callables: Optional[Mapping[str, object]] = None,
    public_builtin_callable_ids: Optional[Tuple[str, ...]] = None,
) -> Compilation:
    template_sandbox = validate_public_template_sandbox(template_sandbox)
    options = RunOptions(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
        resolver_trusted_mode=resolver_trusted_mode,
        components=components,
        sink=sink,
        overrides=overrides,
        guardrails=guardrails,
        loader_retry=loader_retry,
        batch_size=batch_size,
        demand_failure_policy=demand_failure_policy,
        demand_diagnostics=demand_diagnostics,
        parallel_mode=parallel_mode,
        max_workers=max_workers,
        key_normalization=normalize_key_normalization(key_normalization),
        init_vars=init_vars,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
        builtin_callables=builtin_callables,
        public_builtin_callable_ids=public_builtin_callable_ids,
    )
    return _compile(yaml_path, options=options)


__all__ = (
    "compile",
    "run",
)
