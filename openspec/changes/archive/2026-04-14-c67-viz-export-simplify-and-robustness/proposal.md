## Why

Viz 导出（`viz_snapshot.json` + `viz_events.jsonl`/`viz_trace.jsonl`）的定位是“开发辅助/可观测性回放”，但在服务端或高并发场景下它仍会进入运行期路径，并可能成为额外的锁热点与 IO 热点：

- 当前 JSONL 写出采用 per-emitter 的 `threading.Lock`，并在每条事件写入后立即 `flush()`；在高频事件/多线程触发下容易放大 contention 与尾延迟；
- 并发写出路径需要更明确的“可解析性”契约，避免半写/交错导致 JSONL 损坏（尤其在并发/重入情况下）。

`openspec/notplan-changes/c20-lockless-cache-and-viz` 已明确了组 C（viz/observability 输出）的目标：收敛写出串行化边界、减少显式锁依赖、并强化并发下文件完整性。本变更将该目标落为可实施的设计与任务。

## What Changes

- 收敛 viz JSONL 写出边界：将事件写出集中到“单写者”（或等价的 capture+replay/flush）路径，减少显式锁竞争。
- 强化并发下文件完整性：
  - `viz_snapshot.json` 继续保持原子写入（temp+replace）；
  - `viz_events.jsonl`/`viz_trace.jsonl` 在并发/重入下 MUST 始终可解析（不产生半行/交错 JSON）。
- 在不改变对外语义的前提下做性能优化：减少锁持有时间与不必要的 IO 交错（实现细节在 design 中收敛）。
- 保持导出格式与路径约定不变（`vizevent/v1`、默认目录 `scalim-viz/<run_id>/...` 等）；不涉及 viz 前端合并/迁移到 VSCode 插件的工作。

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `flow-visualization`: 强化 viz JSONL 事件流在并发/重入下的可解析性与写出串行化契约（不改变事件结构）。
- `observer-concurrency-contract`: 明确 file-based observers（尤其 viz）在并发执行下的默认安全保障与单写者边界。

## Impact

- 受影响代码（预期）：
  - `src/scalim/ob/presets/_internal/viz_output.py`（JSONL emitter 写出策略收敛）
  - `src/scalim/ob/presets/_internal/viz_handlers.py`（如需调整 emit 调用边界/批量策略）
  - `tests/ob/test_viz_hook.py` 等并发/完整性相关测试（回归护栏）
- 对用户的影响：
  - 输出格式与配置面尽量保持不变；
  - 运行期性能与稳定性预期提升（降低锁竞争、降低文件损坏/半写风险）。

