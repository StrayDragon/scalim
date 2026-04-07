## Context

当前 YAML DSL 对外存在两条“执行入口”：

- demand：`scalim.dsl.by_yaml.run(yaml_path, *, options: RunOptions)`
- workflow：`scalim.dsl.by_yaml.run_workflow(...)`

其中 demand 入口已经完成 “kwargs → `RunOptions`” 的收敛；但 workflow 入口仍然保留了一个长 kwargs 列表，并在内部重新组装 `RunOptions`：

- 形成重复的 public API surface（同一 knob 同时存在于 `RunOptions` 与 `run_workflow` kwargs）
- 增大 drift 风险（新增 knob 时需要两处改动 + 两处文档同步）
- 增大循环依赖风险（入口为了“方便导出/引用”容易引入跨层 import）

同时，workflow 生命周期编排已经明确存在 SSOT：
`run_workflow_lifecycle_until_preflight(..., base_options: RunOptions, ...)`，
这意味着 `run_workflow` 保留重复 kwargs 并没有带来额外能力，只是额外维护成本。

约束：

- 运行时必须兼容 Python 3.6。
- 不做兼容层/双入口；本次为明确的破坏性收敛。
- 需要避免通过“把所有东西搬到一个文件里”来消除重复，必须保持模块分层清晰以避免循环导入。
- 文档与规范需跟随真实代码入口同步，且生成物治理规则不变（`*.gen.*` / injected blocks 禁止手改）。

## Goals / Non-Goals

**Goals:**

- `RunOptions` 成为 demand/workflow 共享的唯一 runtime knobs 承载对象。
- `run_workflow` 不再重组装 `RunOptions`，只做 workflow-scope 编排与依赖注入。
- demand/workflow 两个入口复用同一套 `RunOptions` 公开归一化逻辑，避免行为差异。
- 最大限度降低循环导入风险（显式把共享逻辑放在 “runtime 子包” 的单向依赖方向上）。

**Non-Goals:**

- 不引入新的 workflow DSL 字段或新的 runtime knobs。
- 不在本次变更中引入 “per-run sink” 等新扩展面（这需要额外的生命周期/关闭语义设计）。
- 不为旧 kwargs 提供长期兼容转发（不做 shim；仓库内一次性升级）。

## Decisions

### Decision 1: `run_workflow` 收敛为 `options: RunOptions`

将 workflow 的稳定入口定义为：

```python
def run_workflow(
    workflow_yaml_path: str,
    *,
    options: RunOptions,
    run_patches_by_id: Optional[Mapping[str, WorkflowRunPatch]] = None,
    workflow_resources_wait: Optional[WorkflowResourcesWaitOptions] = None,
    workflow_output_staging: Optional[WorkflowOutputStagingOptions] = None,
    path_aliases: Optional[Mapping[str, str]] = None,
    run_ir_fn: Optional[Callable[..., ExecutionResult]] = None,
    compile_demand_yaml_fn: Optional[Callable[..., _CompilationLike]] = None,
) -> WorkflowResult: ...
```

解释：

- `RunOptions` 承载所有 “demand 运行期 knobs”（allowlist、模板、并行、重试、护栏、overrides、batch_size、diagnostics 等）。
- workflow-scope 参数保持独立（它们不属于单个 demand 的运行期 knobs）。
- `run_ir_fn/compile_demand_yaml_fn` 继续作为显式依赖注入 seam（每次调用级别，不通过 module-global mutation）。

### Decision 2: 共享 `RunOptions` 归一化逻辑（demand/workflow 同步）

新增一个 runtime 内部 SSOT（例如 `src/scalim/dsl/by_yaml/runtime/normalize.py`），提供：

- `normalize_public_run_options(options: RunOptions) -> RunOptions`

并在：

- `src/scalim/dsl/by_yaml/runtime/entrypoints.py:run/compile`
- `src/scalim/dsl/by_yaml/workflow_entrypoints.py:run_workflow`

中复用，以统一：

- `template_sandbox` 的公开值校验/归一化
- `key_normalization` 的标准化
- `max_workers` 的类型归一化（`int`）

注意：normalize 模块必须保持单向依赖（只依赖 `runtime.contracts` 与底层 util），不得反向依赖 workflow 入口模块，避免循环导入。

### Decision 3: workflow 暂不支持 `RunOptions.sink`（fail-fast）

workflow 会对每个 demand run 执行一次 `run_ir(...)`，并在每次执行结束时关闭 sink。若允许用户传入同一个 `sink` 实例作为全局选项，
会导致：

- 第一个 run 结束时 sink 被关闭，后续 runs 复用同一对象会行为不确定/直接失败
- 或要求 sink 具备“可重复 close/可重入写入”的额外契约（当前并无该契约）

因此本次收敛中：

- `run_workflow(..., options=RunOptions(sink=...))` MUST fail-fast，并给出明确迁移提示：
  - 若需要 per-run sink，未来应引入 `sink_factory`（可能位于 `WorkflowRunPatch` 或 workflow-scope options）而不是复用单实例。

### Decision 4: facade 仍保持稳定导入路径，但不扩大额外入口

- `scalim.dsl.by_yaml.run_workflow` 保持为官方 facade；
- `scalim.dsl.by_yaml.workflow_entrypoints.run_workflow` 仍可作为稳定实现路径导入（但示例/文档优先使用 facade）；
- 不新增新的 “legacy kwargs wrapper” 模块，避免变成新的兼容面与循环依赖源。

## Risks / Trade-offs

- [破坏性升级] 下游需要把 `run_workflow(..., batch_size=..., guardrails=...)` 迁移为 `RunOptions(...)`。→ 缓解：仓库内所有示例/测试/文档一次性升级；OpenSpec delta specs 给出明确的新签名形态。
- [sink 语义] 用户可能希望 workflow 也支持 sink。→ 缓解：本次 fail-fast；在后续专门变更中以 `sink_factory` 形式引入（可测试且语义明确）。
- [归一化行为变化] workflow 入口此前未完全复用 demand 入口的归一化路径。→ 缓解：将归一化视为 “行为对齐”，并补齐最小回归覆盖（例如 key_normalization 规范化）。
- [循环导入] 共享逻辑抽取不当会引入 import 环。→ 缓解：normalize 放在 `runtime/` 子包且只依赖 contracts + util；workflow 入口只向下依赖 runtime。

## Migration Plan

1. 实现新的 `run_workflow(..., options=RunOptions)` 签名，并删除旧 kwargs（不保留兼容 shim）。
2. 抽取并复用 `normalize_public_run_options`，让 demand/workflow 入口一致。
3. 仓库内所有调用点一次性升级（tests/docs/notebooks/skills/specs）。
4. 更新 OpenSpec delta specs，并通过 `just openspec-check` 验收。
5. 如涉及 docs 生成页或 injected blocks，更新 SSOT 并运行 `just gen-docs`，再通过 `just qa` 的 drift gate。

## Open Questions

- `sink_factory` 的最佳落点：放入 `WorkflowRunPatch`（per-run）还是 workflow-scope 的新 options 对象？（本次不实现，仅作为后续演进点记录）
> 我认为是 `WorkflowRunPatch` 只是我们先 fast-failed 这次先不处理 等我们之后标准化api后再说
