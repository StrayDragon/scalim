from typing import Dict, FrozenSet, List, Optional, Union

from ....execution.guardrails import GuardrailsPolicy
from ....execution.loader_retry import LoaderRetryPoliciesSpec
from ....execution.output_composition import OutputCompositionSpec
from ....execution.run_ir import run_ir
from ....hooks.base import IExecutionHook
from ....ob.observer import Observer
from ....sinks.sink_base import ISink
from ....typedefs import ParallelMode
from .compiler import compile as _compile
from .contracts import Compilation, RunOptions, RunOverrides, RunResult


def run(
    yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    components: Optional[List[Union[Observer, IExecutionHook]]] = None,
    sink: Optional[ISink] = None,
    output_composition: Optional[OutputCompositionSpec] = None,
    overrides: Optional[RunOverrides] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    loader_retry: Optional[LoaderRetryPoliciesSpec] = None,
    batch_size: Optional[int] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    runtime_vars: Optional[Dict[str, object]] = None,
) -> RunResult:
    """运行 `YAML DSL`,并支持显式覆盖项与输出 `sink`.

    优先级(高 -> 低):
    - `overrides.*`(仅对未设为 `UNSET` 的字段生效)
    - 配置文件中的 `output.*`
    - 执行默认值

    注意:
    - `overrides.output.path=None` 会禁用文件输出,即使 `YAML` 设置了 `output.path`.
    - `overrides.viz_config` 可启用/禁用 `viz`,不受 `YAML` 的 `observability.viz.*` 影响.
    - 输出数据的保留完全由 `sink=...`(例如 `InMemoryRowSink`)决定,而不是由布尔开关控制.
    """
    options = RunOptions(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
        components=components,
        sink=sink,
        output_composition=output_composition,
        overrides=overrides,
        guardrails=guardrails,
        loader_retry=loader_retry,
        batch_size=batch_size,
        parallel_mode=parallel_mode,
        max_workers=max_workers,
        runtime_vars=runtime_vars,
    )
    compilation = _compile(yaml_path, options=options)
    core = run_ir(compilation.demand_ir, compilation.request)
    return RunResult(core, config=compilation.config, yaml_path=yaml_path, sink=sink)


def compile(  # noqa: A001
    yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    components: Optional[List[Union[Observer, IExecutionHook]]] = None,
    sink: Optional[ISink] = None,
    output_composition: Optional[OutputCompositionSpec] = None,
    overrides: Optional[RunOverrides] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    loader_retry: Optional[LoaderRetryPoliciesSpec] = None,
    batch_size: Optional[int] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    runtime_vars: Optional[Dict[str, object]] = None,
) -> Compilation:
    options = RunOptions(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
        components=components,
        sink=sink,
        output_composition=output_composition,
        overrides=overrides,
        guardrails=guardrails,
        loader_retry=loader_retry,
        batch_size=batch_size,
        parallel_mode=parallel_mode,
        max_workers=max_workers,
        runtime_vars=runtime_vars,
    )
    return _compile(yaml_path, options=options)


__all__ = [
    "compile",
    "run",
]
