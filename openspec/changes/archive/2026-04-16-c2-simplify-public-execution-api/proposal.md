## Why

`execution` 层已经提供了 DSL-agnostic 的统一编排入口（概念上是 `run_ir(DemandIr, ExecutionRequest) -> ExecutionResult`），但当前 Tier1 curated public surface（`scalim.execution`）对用户并不友好：

- 对外入口偏“类构造 + 多参数”，缺少与 YAML DSL 一致的“单一 options/request 对象驱动”的心智模型。
- 调用侧要么直接 new `ScalimEngine(...)` 承担大量编排细节，要么深入 `scalim.execution.run_ir` 的实现模块路径，容易把内部路径写进用户材料。

本 change 目标是把 execution 的 public surface 收敛成清晰、稳定、可校验的入口：以 `ExecutionRequest` 作为唯一运行期契约，减少隐式规则与导入路径漂移。

## What Changes

- **BREAKING**：调整 `scalim.execution` 的 Tier1 public surface：
  - 将 `run_ir` 与其 request/result contracts（`ExecutionRequest`/`ExecutionResult` 等）提升为官方推荐入口（curated re-export 或显式列入 Tier1 entrypoints）。
  - 降低或移除 `ScalimEngine` 在默认 public facade 中的“主入口地位”（保留高级用法时也必须有明确的边界与文档说明）。
- 强化 fail-fast：
  - request/options 的非法组合在构造期/校验期直接失败，错误信息指向字段路径（避免执行中晚失败）。
- 同步更新用户材料与回归门禁：
  - public API imports（docs/skills/notebooks/tests）只使用 curated entrypoints
  - public surface 的 `__all__` 漂移必须可审计、可 gate

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `execution-structure`: 明确 execution 层的稳定 public surface（`scalim.execution` 与 `execution.run_ir.__all__`）与推荐入口形态（options-only）。
- `public-api-surface-governance`: curated entrypoints 目录需要新增/调整 execution 侧入口，并通过 import smoke / `__all__` gate 固定。
- `public-api-manifest`: public API catalog/docs 的生成内容需要包含 execution 侧新增的稳定入口与符号集合。

## Impact

- 受影响代码：
  - `src/scalim/execution/__init__.py` 与 `src/scalim/execution/run_ir.py`（public exports 组织与 contracts）
  - YAML DSL 适配层若直接依赖 engine 构造细节，可能需要改为走 `ExecutionRequest`（保持分层清晰）
- 受影响用户材料：
  - docs/skills/notebooks/tests 的导入路径与示例
- 风险：
  - 属于 public surface 变更，需一次性升级全仓调用点（不做兼容层）
