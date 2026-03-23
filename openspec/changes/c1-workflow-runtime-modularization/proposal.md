## Why

workflow 相关实现模块明显超载，出现“单文件聚合多种职责 + 巨型函数 + 复杂度豁免”的维护信号：

- `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`（1600+ 行；`run_workflow` 复杂度豁免）
- `src/scalim/dsl/by_yaml/runtime/workflow_resources.py`（资源写入/导出/事件等多职责混杂）
- `src/scalim/dsl/by_yaml/workflow.py`（配置解析、路径解析、校验等职责叠加）
- CLI 大入口：`src/scalim/cli/yaml_dsl.py`

这种结构会放大以下成本与风险：

- 改动半径大、review 困难，容易引入回归（尤其是 workflow 的并发/失败策略/资源写入等交叉逻辑）
- 层级边界不清导致循环依赖更难避免（by_yaml runtime ↔ execution/ob/hooks 的边界需要更严谨）
- 复杂度豁免变成“长期免检”，新需求继续堆叠，最终难以演进

## What Changes

- 将 workflow runtime 代码按职责拆分为更小的内部模块（保持对外稳定入口不变）
  - 保留稳定入口：`run_workflow(...)` / `validate` / `compile` 等对外函数（现有 import 路径可继续使用）
  - 内部按 phase 拆分：config load/validate → compile IR → schedule/execute → collect/report → bundle/viz
- 收敛巨型函数
  - 将 `run_workflow` 拆为若干可单测的纯函数/小类（例如：`_load_and_compile_workflow_ir`、`_build_runtime_options`、`_execute_workflow_plan` 等）
  - 逐步移除 `# noqa: C901/PLR0915/...` 豁免（或把豁免局限在极少数 glue 层）
- 资源模块拆分
  - 将 sheetbook/workbook/csv 等资源写入与导出逻辑分离到子模块（减少 `workflow_resources.py` 的职责密度）
  - 明确“持锁范围 vs 外部回调/emit”的约束（与 c0 deadlock 提案一致）
- 增加 refactor 护栏
  - 用单元测试覆盖关键不变量（失败策略、并发上限、ctx 可见性、writes 顺序/冲突策略）
  - 增加 import/模块边界的最小 smoke test（防止拆分后稳定入口被破坏）

## Capabilities

### New Capabilities
- `workflow-runtime-module-organization`: 定义 workflow runtime 的职责分层与稳定入口约束（哪些模块属于稳定入口、哪些属于内部实现、以及拆分/迁移的准则）。

### Modified Capabilities
- `module-organization`: 将 workflow runtime 相关路径纳入“热点模块持续治理对象”，并要求持续避免单文件职责聚合与复杂度豁免蔓延。

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources.py`
  - `src/scalim/dsl/by_yaml/workflow.py`
  - `src/scalim/cli/yaml_dsl.py`
- 预期对外行为不变，但会产生大量文件移动/拆分；需要以测试与 `just qa` 作为回归护栏
