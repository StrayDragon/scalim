## Why

`batch_size` 是当前 YAML DSL 运行期性能/内存权衡中最关键的 runtime policy 之一，但只能通过 Python 入口注入：

- 全局：`RunOptions(batch_size=...)`
- workflow per-run：`run_options_patches_by_run_id={"<run_id>": WorkflowRunOptionsPatch(batch_size=...)}`

在包含多种 demand profile（source 数量差异大、lookup-heavy vs pure streaming、行宽差异大）的 workflow 中：

- 最优 `batch_size` 取决于数据体量与运行期行为（批次数、每批 lookup 开销、内存峰值），只能反复试跑调参；
- 调用侧需要硬编码 run_id → batch_size 映射，需求结构变动后维护成本高；
- 环境变量调参缺少结构化指导，难以形成“可解释”的推荐与标准化策略。

同时，scalim 核心很难在不执行 loader 的情况下“自动知道总行数”（main_source 返回的是通用 `Iterable`/generator，无法泛化 `len()`），但调用侧通常具备 DB `COUNT(*)` 或 estimate 能力，且更愿意把这类 I/O 放在 Python 侧可控地执行。

在既有 “runtime policy MUST move out of YAML mainline” 的边界约束下（`batch_size` 不能回到 YAML authoring surface），本提案选择扩展现有 hooks/events 体系：在进入 `run_ir()` 之前提供一个**policy signal（decision event）阶段点**，由 hook 捕获并改写候选值，从而把 “预检/估算/策略” 收敛到 Python hook 里实现；当调用方显式指定 `batch_size` 时，框架应跳过该 signal（保持现有直觉与可控性）。

## What Changes

- **不新增任何 YAML authoring 字段**（保持 runtime policy boundary；避免 schema/LSP 维护成本）。
- 在 runtime entrypoints 增加一个可选的 **policy signal 阶段**：位于 compile 产物就绪之后、调用 `run_ir()` 之前。
- v0 新增一个 decision signal：`pre_use_batch_size`。
  - 输入：当前候选 `batch_size`（来自 config/default；仅在 `RunOptions.batch_size is UNSET` 时触发）。
  - 输出：hook 可对该候选值做改写（例如：执行一次 `COUNT(*)` 估算 total_rows，再按策略反推 batch_size，并做 clamp）。
- 预留后续信号（仅做设计占位，不要求 v0 落地）：`pre_use_max_workers`、`pre_use_lookup_chunk_size` 等。
- signal 与 hook 组合语义：
  - hook 以稳定顺序（`components` 注册顺序）依次接收该 signal；
  - signal payload 为“可改写的 decision 对象”，记录改写历史与原因，便于 pre-run_ir 诊断与调试；
  - 当调用方显式设置 `batch_size`（`RunOptions` 或 workflow per-run patch）时，框架 MUST 跳过该 signal（不做任何外部 I/O）。

## Capabilities

### New Capabilities
- `hooks-events`: 新增 policy decision signal（例如 `pre_use_batch_size`），允许 hook 在 pre-run_ir 阶段改写候选 runtime policy 值（v0）。

### Modified Capabilities
- `yaml-dsl-runtime-policy-boundary`: 澄清边界：`batch_size` 仍 MUST 迁出 YAML；系统允许通过 runtime hooks 在 pre-run_ir 边界推导 derived 值，但不得降低调用方显式控制（显式值永远胜出）。
- `dsl-runtime-structure`: 增加 `run()/run_workflow()` 的 policy signal 阶段语义（在进入 engine 前、在 effective runtime policy 边界内执行）。

## Impact

- **YAML authoring surface**：无变化。
- **Runtime behavior**：当调用方挂载了相关 hook 且未显式提供 `batch_size` 时，pre-run_ir 阶段可能会执行一次额外 I/O（例如 COUNT/estimate）；当显式提供 `batch_size` 时，不触发 signal，不引入额外开销。
- **代码影响面**（预期）：hooks/events（新增 signal 与 payload）、runtime entrypoints（新增 pre-run_ir 阶段）、workflow runner（per-run 注入上下文）、日志/诊断输出、测试。
- **文档治理**：更新 hooks/events 与 runtime policy 的最佳实践文档与示例（Python 侧如何挂载 hook、如何在 hook 中做 total_rows 估算与 clamp）。
