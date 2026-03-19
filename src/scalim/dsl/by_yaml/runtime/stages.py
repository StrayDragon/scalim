"""显式划分 `YAML` 运行时编译的阶段边界.

阶段:
1)`allowlist` 校验
2)`YAML` 解析
3)配置 -> `IR` 转换
4)执行请求映射
"""

from dataclasses import dataclass
from typing import FrozenSet, Mapping, Optional

from ....execution.run_ir import ExecutionRequest
from ....spec.ir.demand import DemandIr
from ..schema_dsl.models import DemandConfig
from .compiler import (
    build_request,
    compile_ir,
    create_reference_resolver,
    load_config,
    validate_allowlist,
)
from .contracts import RunOptions
from .references import SecurePythonReferenceResolver


def stage_validate_allowlist(*, allowed_modules: FrozenSet[str], allowed_functions: Optional[FrozenSet[str]]) -> None:
    validate_allowlist(allowed_modules=allowed_modules, allowed_functions=allowed_functions)


class StageAllowlistMismatchError(ValueError):
    MESSAGE: str = "Stage context allowlist must match RunOptions allowlist"

    def __init__(self) -> None:
        super(StageAllowlistMismatchError, self).__init__(self.MESSAGE)


@dataclass(frozen=True)
class YamlDslStageContext:
    allowed_modules: FrozenSet[str]
    allowed_functions: Optional[FrozenSet[str]]
    resolver: SecurePythonReferenceResolver


def stage_create_context(*, allowed_modules: FrozenSet[str], allowed_functions: Optional[FrozenSet[str]]) -> YamlDslStageContext:
    stage_validate_allowlist(allowed_modules=allowed_modules, allowed_functions=allowed_functions)
    resolver = create_reference_resolver(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
    )
    return YamlDslStageContext(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
        resolver=resolver,
    )


def stage_load_yaml_config(yaml_path: str, *, template_vars: Optional[Mapping[str, object]] = None) -> DemandConfig:
    return load_config(yaml_path, template_vars=template_vars)


def stage_compile_demand_ir(config: DemandConfig, *, context: YamlDslStageContext) -> DemandIr:
    return compile_ir(config, resolver=context.resolver)


def stage_build_execution_request(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    options: RunOptions,
    context: YamlDslStageContext,
) -> ExecutionRequest:
    if options.allowed_modules != context.allowed_modules or options.allowed_functions != context.allowed_functions:
        raise StageAllowlistMismatchError
    return build_request(config, demand_ir, options=options, resolver=context.resolver)


__all__ = [
    "StageAllowlistMismatchError",
    "YamlDslStageContext",
    "stage_build_execution_request",
    "stage_compile_demand_ir",
    "stage_create_context",
    "stage_load_yaml_config",
    "stage_validate_allowlist",
]
