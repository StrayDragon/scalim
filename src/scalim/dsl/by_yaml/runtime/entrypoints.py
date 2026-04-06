from ....execution.key_normalization import normalize_key_normalization
from ....execution.run_ir import run_ir
from ....vendor.dataclassesx import replace
from .._public_template_sandbox import validate_public_template_sandbox
from .compiler import compile as _compile
from .contracts import Compilation, RunOptions, RunResult


def _normalize_public_run_options(options: RunOptions) -> RunOptions:
    template_sandbox = validate_public_template_sandbox(options.template_sandbox)
    key_normalization = normalize_key_normalization(options.key_normalization)
    max_workers = int(options.max_workers)
    if (
        template_sandbox == options.template_sandbox
        and key_normalization == options.key_normalization
        and max_workers == options.max_workers
    ):
        return options
    return replace(
        options,
        template_sandbox=template_sandbox,
        key_normalization=key_normalization,
        max_workers=max_workers,
    )


def run(
    yaml_path: str,
    *,
    options: RunOptions,
) -> RunResult:
    """运行 `YAML DSL` 官方入口.

    优先级(高 -> 低):
    - `options.overrides.outputs`(完全覆盖 `YAML` 的 `outputs`; 整体替换,即 `replace`; 非空)
    - `YAML` 的 `outputs`(若声明)
    - 执行默认值

    注意:
    - YAML 主线不再支持 `observability.*`(旧字段会发出迁移告警并被忽略);可观测性通过 `components=[Observer()/Hook()]` 与
      `RunOptions(components=[...], overrides=RunOverrides(viz_config=VizObserverConfig(...)))` 装配.
    - `options.overrides.viz_config` 可启用/禁用 `viz` 并控制落盘路径、`trace` 输出与 `payload_policy` 策略等.
    - 当 `options.overrides.outputs` 把 `YAML` 中的 `workbook` 输出整体替换为非 `workbook` 输出时,未显式设置 `path` 的 `meta/audit`
      会被跳过;若仍需保留,请为 `meta.path` / `audit.path` 提供独立 `workbook` 路径.
    - 输出数据的保留完全由 `options.sink`(例如 `InMemoryRowSink`)决定,而不是由布尔开关控制.
    """
    options = _normalize_public_run_options(options)
    compilation = _compile(yaml_path, options=options)
    core = run_ir(compilation.demand_ir, compilation.request)
    return RunResult(core, config=compilation.config, yaml_path=yaml_path, sink=options.sink)


def compile(  # noqa: A001
    yaml_path: str,
    *,
    options: RunOptions,
) -> Compilation:
    options = _normalize_public_run_options(options)
    return _compile(yaml_path, options=options)


__all__ = (
    "compile",
    "run",
)
