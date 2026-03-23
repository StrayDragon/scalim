## Why

Scalim 的核心卖点是“可控内存占用 + 高吞吐执行”。当前执行层虽已具备剪枝/流式输出等能力，但仍存在一些热路径的可避免开销与高频分配（尤其在关联/大批次场景），导致吞吐与 RSS 峰值不够理想，且缺少强约束的回归护栏。

现在推进一次 A→B→C 的渐进式性能优化：先用 c0 级护栏锁住不回归，再逐步引入更激进的数据结构与接口优化。

## What Changes

- A：Hotpath 级优化（更严格的 wants-gated + 更少临时分配）
  - 对“未订阅的诊断/观测事件”路径做更彻底的短路，避免无意义的逐行/逐键循环与 payload 辅助构造。
  - 将热点逻辑（如 relation lookup 诊断、row/column 写出前的中间结构构造）收敛为可测、可基准的单元。
- B：BatchContext 存储结构优化（Dense path）
  - 在不改变语义的前提下，为批次内连续 `row_id` 引入更低开销的存储表示，显著降低哈希表开销与对象数量，减少内存占用并提升速度。
  - 覆盖 `adaptive` overlay context 等相关路径，保证行为一致。
- C：输出 sink 写入 fastpath（减少 dict 构造/拷贝）
  - 为行式/列式 sink 定义可选的“对齐数组/序列”写入 fastpath，让 pipeline 能在保持语义一致的情况下减少中间 dict 构造与复制。
  - 内建 sinks 升级使用 fastpath；外部 sinks 可继续使用现有接口（fastpath 为可选能力）。
- c0 护栏：防回归与可观测
  - 建立可重复的性能/内存基线采集流程（bench + memray），并提供最小可运行的回归门禁入口（本地与 CI 皆可用/可选）。

## Capabilities

### New Capabilities
- `perf-regression-guardrails`: 定义性能/内存基线、采集方法与回归门禁（基于 `tests/bench/` 与 `just bench*` 入口，含 memray 剖析）。
- `dense-batch-context`: 定义批次上下文在“连续 row_id”场景的等价语义与性能约束（Dense path 的可用条件、边界与回退）。
- `sink-fastpath`: 定义可选的 sink fastpath 接口（行/列写入的对齐序列形态）以及 pipeline 的选择策略。

### Modified Capabilities
- `hooks-observability-structure`: 细化 wants-gated 的热路径语义，明确当 `wants(event_type)=false` 时不得引入逐行/逐键的额外计算与分配（不仅是不构造 `Event` envelope）。
- `sinks-contracts`: 在保持现有接口可用的前提下，增加 fastpath 的可选契约与一致性要求（内建 sinks 必须覆盖该路径）。

## Impact

- 执行层：`src/scalim/execution/`（BatchContext、LoadRef、Pipeline、adaptive overlay）会有结构性改动与新增基准覆盖。
- 可观测性：`src/scalim/ob/` 的 wants-gated 语义将被强化并纳入回归测试/基准。
- 输出层：`src/scalim/sinks/` 可能新增可选 fastpath 接口/实现以减少分配；内建 sinks 会同步升级。
- 工程护栏：`tests/bench/`、`justfile`、CI（可选）将新增/强化性能回归门禁入口；OpenSpec 工件需通过 `just openspec-check` 校验。

