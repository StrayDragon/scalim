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
from ....hooks.policy_signals import PreUseBatchSizeDecision, emit_pre_use_batch_size_signal
from ....ob.components import split_components
from ....ob.observer import Observer
from ....sinks import ISink
from ....typedefs import KeyNormalizationMode, ParallelMode
from ....vendor.dataclassesx import replace
from .._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from .compiler import compile as _compile
from .contracts import (
    UNSET,
    Compilation,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunResult,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    ResolverTrustedMode,
    RunOverrides,
    UnsetType,
)

_unsafe_logger = logging.getLogger("scalim.dsl.yaml_dsl.unsafe")
_policy_logger = logging.getLogger("scalim.dsl.yaml_dsl.unsafe.policy")

warnings.warn(
    "`unsafe_entrypoints` 为内部/不安全 `API`;请优先使用 `scalim.dsl.yaml_dsl.run/compile`; `legacy` 沙箱已弃用,请用 `safe`.",
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
    batch_size: Union[Optional[int], UnsetType] = UNSET,
    demand_failure_policy: Optional[str] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    key_normalization: KeyNormalizationMode = "raw",
    init_vars: Optional[Dict[str, object]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
) -> DemandRunResult:
    """不安全入口: 允许显式启用 `legacy` 模板沙箱等能力.

    仅用于可信输入/内部测试;普通用户请使用 `scalim.dsl.yaml_dsl.run`.
    """
    sandbox = _validate_unsafe_template_sandbox(template_sandbox)
    _audit_unsafe_call("unsafe_run", template_sandbox=sandbox)
    options = DemandRunOptions(
        security=DemandRunSecurityOptions(
            allowed_modules=allowed_modules,
            allowed_functions=allowed_functions,
            resolver_trusted_mode=resolver_trusted_mode,
            allowed_yaml_roots=allowed_yaml_roots,
        ),
        template=DemandRunTemplateOptions(
            template_vars=template_vars,
            template_sandbox=sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
            init_vars=init_vars,
        ),
        runtime=DemandRunRuntimeOptions(
            components=components,
            guardrails=guardrails,
            loader_retry=loader_retry,
            batch_size=batch_size,
            demand_failure_policy=demand_failure_policy,
            parallel_mode=parallel_mode,
            max_workers=max_workers,
            key_normalization=normalize_key_normalization(key_normalization),
        ),
        outputs=DemandRunOutputOptions(overrides=overrides),
    )
    compilation = _compile(yaml_path, options=options)

    request = compilation.request
    if isinstance(options.runtime.batch_size, UnsetType):
        _observers, hooks = split_components(request.components)
        runtime_bindings = request.runtime_bindings
        main_source_id = compilation.demand_ir.main_source.source_id
        main_loader = None if runtime_bindings is None else runtime_bindings.main_source_loaders.get(str(main_source_id))
        decision = PreUseBatchSizeDecision(
            value=request.batch_size,
            demand_path=str(yaml_path),
            init_vars=options.template.init_vars,
            main_loader=main_loader,
        )
        emit_pre_use_batch_size_signal(hooks, decision)
        request = replace(request, batch_size=decision.value)

        if decision.history:
            _policy_logger.info("`pre_use_batch_size` 决策完成: 批大小=%s 改写轨迹=%s", decision.value, decision.history)
        else:
            _policy_logger.debug("`pre_use_batch_size` 决策完成: 批大小=%s 改写轨迹=%s", decision.value, decision.history)

    if sink is not None:
        request = replace(request, sink=sink)
    core = run_ir(compilation.demand_ir, request)
    return DemandRunResult(core, config=compilation.config, yaml_path=yaml_path, captured_rows=None)


def unsafe_compile(  # noqa: PLR0913
    yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    resolver_trusted_mode: ResolverTrustedMode = ResolverTrustedMode.STRICT_ALLOWLIST,
    components: Optional[List[Union[Observer, IExecutionHook]]] = None,
    overrides: Optional[RunOverrides] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    loader_retry: Optional[LoaderRetryPoliciesSpec] = None,
    batch_size: Union[Optional[int], UnsetType] = UNSET,
    demand_failure_policy: Optional[str] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    key_normalization: KeyNormalizationMode = "raw",
    init_vars: Optional[Dict[str, object]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
) -> Compilation:
    """不安全入口: 允许显式启用 `legacy` 模板沙箱等能力.

    仅用于可信输入/内部测试;普通用户请使用 `scalim.dsl.yaml_dsl.compile`.
    """
    sandbox = _validate_unsafe_template_sandbox(template_sandbox)
    _audit_unsafe_call("unsafe_compile", template_sandbox=sandbox)
    options = DemandRunOptions(
        security=DemandRunSecurityOptions(
            allowed_modules=allowed_modules,
            allowed_functions=allowed_functions,
            resolver_trusted_mode=resolver_trusted_mode,
            allowed_yaml_roots=allowed_yaml_roots,
        ),
        template=DemandRunTemplateOptions(
            template_vars=template_vars,
            template_sandbox=sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
            init_vars=init_vars,
        ),
        runtime=DemandRunRuntimeOptions(
            components=components,
            guardrails=guardrails,
            loader_retry=loader_retry,
            batch_size=batch_size,
            demand_failure_policy=demand_failure_policy,
            parallel_mode=parallel_mode,
            max_workers=max_workers,
            key_normalization=normalize_key_normalization(key_normalization),
        ),
        outputs=DemandRunOutputOptions(overrides=overrides),
    )
    return _compile(yaml_path, options=options)


__all__ = (
    "unsafe_compile",
    "unsafe_run",
)
