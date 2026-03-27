"""YAML DSL 非公共入口: `unsafe` 扩展点.

注意:
- 该模块属于内部/不稳定路径,不应在 `docs`/`examples`/`skills` 中作为官方导入路径推广.
- 该模块允许显式启用不安全能力(例如 `legacy` 模板沙箱),仅用于可信输入/内部测试.
- `legacy` 模板沙箱计划逐步废弃,请迁移到 `safe` 模式.
"""

import logging
import traceback
import warnings
from typing import Dict, FrozenSet, List, Mapping, Optional, Tuple, Union

from ....execution.guardrails import GuardrailsPolicy
from ....execution.key_normalization import normalize_key_normalization
from ....execution.loader_retry import LoaderRetryPoliciesSpec
from ....execution.run_ir import run_ir
from ....hooks import IExecutionHook
from ....ob.observer import Observer
from ....sinks import ISink
from ....typedefs import KeyNormalizationMode, ParallelMode
from .compiler import compile as _compile
from .contracts import Compilation, ResolverTrustedMode, RunOptions, RunOverrides, RunResult

_unsafe_logger = logging.getLogger("scalim.dsl.by_yaml.unsafe")

warnings.warn(
    "`unsafe_entrypoints` 为内部/不安全 `API`;请优先使用 `scalim.dsl.by_yaml.run/compile`; `legacy` 沙箱已弃用,请用 `safe`.",
    DeprecationWarning,
    stacklevel=2,
)


def _validate_unsafe_template_sandbox(template_sandbox: str) -> str:
    value = str(template_sandbox or "").strip() or "safe"
    if value not in {"safe", "legacy"}:
        msg = "`template_sandbox` 必须是以下值之一: `safe`, `legacy`"
        raise ValueError(msg)
    return value


def _audit_unsafe_call(fn_name: str, *, template_sandbox: str) -> None:
    if template_sandbox == "legacy":
        warnings.warn(
            "`template_sandbox='legacy'` 已弃用;请迁移到 `template_sandbox='safe'`.",
            DeprecationWarning,
            stacklevel=3,
        )
    caller = "".join(traceback.format_stack(limit=4)[:-1]).strip()
    _unsafe_logger.warning(
        "`unsafe` 入口被调用: `fn`=%s `template_sandbox`=%s\n`caller`:\n%s",
        fn_name,
        template_sandbox,
        caller,
    )


def unsafe_run(  # noqa: PLR0913
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
    batch_size: Optional[int] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    key_normalization: KeyNormalizationMode = "raw",
    init_vars: Optional[Dict[str, object]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
) -> RunResult:
    """不安全入口: 允许显式启用 `legacy` 模板沙箱等能力.

    仅用于可信输入/内部测试;普通用户请使用 `scalim.dsl.by_yaml.run`.
    """
    sandbox = _validate_unsafe_template_sandbox(template_sandbox)
    _audit_unsafe_call("unsafe_run", template_sandbox=sandbox)
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
        parallel_mode=parallel_mode,
        max_workers=max_workers,
        key_normalization=normalize_key_normalization(key_normalization),
        init_vars=init_vars,
        template_vars=template_vars,
        template_sandbox=sandbox,
        allowed_yaml_roots=allowed_yaml_roots,
    )
    compilation = _compile(yaml_path, options=options)
    core = run_ir(compilation.demand_ir, compilation.request)
    return RunResult(core, config=compilation.config, yaml_path=yaml_path, sink=sink)


def unsafe_compile(  # noqa: PLR0913
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
    batch_size: Optional[int] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    key_normalization: KeyNormalizationMode = "raw",
    init_vars: Optional[Dict[str, object]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
) -> Compilation:
    """不安全入口: 允许显式启用 `legacy` 模板沙箱等能力.

    仅用于可信输入/内部测试;普通用户请使用 `scalim.dsl.by_yaml.compile`.
    """
    sandbox = _validate_unsafe_template_sandbox(template_sandbox)
    _audit_unsafe_call("unsafe_compile", template_sandbox=sandbox)
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
        parallel_mode=parallel_mode,
        max_workers=max_workers,
        key_normalization=normalize_key_normalization(key_normalization),
        init_vars=init_vars,
        template_vars=template_vars,
        template_sandbox=sandbox,
        allowed_yaml_roots=allowed_yaml_roots,
    )
    return _compile(yaml_path, options=options)


__all__ = [
    "unsafe_compile",
    "unsafe_run",
]
