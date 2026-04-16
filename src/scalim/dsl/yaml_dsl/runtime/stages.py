"""显式划分 YAML DSL 运行时编译的阶段边界.

阶段:
1)白名单(`allowlist`)校验
2)YAML 解析
3)配置 -> IR 转换
4)运行时链接(生成 `RuntimeBindings`)
5)执行请求映射
"""

from typing import FrozenSet, Mapping, Optional

from ....exceptions import ScalimYamlError
from ....execution.run_ir import ExecutionRequest
from ....spec.ir import DemandIr
from ....vendor.dataclassesx import dataclass
from ..schema_dsl.models import DemandConfig
from .compiler import (
    build_request,
    compile_ir,
    create_reference_resolver,
    load_config,
    validate_allowlist,
)
from .contracts import DemandRunOptions
from .references import SecurePythonReferenceResolver
from .runtime_linking import resolve_runtime_bindings


def stage_validate_allowlist(*, allowed_modules: FrozenSet[str], allowed_functions: Optional[FrozenSet[str]]) -> None:
    validate_allowlist(allowed_modules=allowed_modules, allowed_functions=allowed_functions)


class ScalimStageAllowlistMismatchError(ScalimYamlError):
    MESSAGE: str = "Stage context allowlist must match DemandRunOptions.security allowlist"

    def __init__(self) -> None:
        super(ScalimStageAllowlistMismatchError, self).__init__(self.MESSAGE)


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
    _ = context
    return compile_ir(config)


def stage_build_execution_request(
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    yaml_base_dir: str,
    options: DemandRunOptions,
    context: YamlDslStageContext,
) -> ExecutionRequest:
    if options.security.allowed_modules != context.allowed_modules or options.security.allowed_functions != context.allowed_functions:
        raise ScalimStageAllowlistMismatchError
    runtime_bindings = resolve_runtime_bindings(demand_ir, resolver=context.resolver)
    return build_request(
        config,
        demand_ir,
        yaml_base_dir=str(yaml_base_dir),
        options=options,
        resolver=context.resolver,
        runtime_bindings=runtime_bindings,
    )


__all__ = (
    "ScalimStageAllowlistMismatchError",
    "YamlDslStageContext",
    "stage_build_execution_request",
    "stage_compile_demand_ir",
    "stage_create_context",
    "stage_load_yaml_config",
    "stage_validate_allowlist",
)
