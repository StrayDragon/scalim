## Context

当前 viz 导出实现包含两类写出：

- snapshot：`viz_snapshot.json`，已采用 temp+replace 的原子写入策略，并有并发读写可解析性测试兜底；
- event stream：`viz_events.jsonl` 与 `viz_trace.jsonl`，当前写出策略为：
  - 多线程调用 `emit()`
  - per-emitter `threading.Lock` 保护文件句柄写入
  - 每条事件写入后立即 `flush()`

这在高频/并发事件场景下容易形成锁热点与 IO 热点，同时我们希望更明确“并发下文件可解析性”的契约边界，使导出更稳健、实现更干净。

本设计遵循 `openspec/notplan-changes/c20-lockless-cache-and-viz` 的组 C 方向：收敛写出串行化边界（single writer 或等价机制），减少显式锁依赖，并保证并发下文件完整性。

## Goals / Non-Goals

**Goals:**

- 对 JSONL 写出实现“单写者”边界：并发触发的事件写入 MUST 串行化到一个写出路径，避免多线程直接写文件造成竞争与交错风险。
- 在不改变对外数据结构的前提下，减少锁竞争与 IO 交错，使 viz 导出更适合服务端/高并发场景。
- 明确并发下文件完整性契约：
  - snapshot 必须原子写且可解析；
  - JSONL 必须不产生半行/交错 JSON（已写入的部分永远可逐行解析）。
- 通过单元测试/并发回归测试提供可验证护栏。

**Non-Goals:**

- 不改变 `vizevent/v1` 的字段结构与文件命名约定。
- 不引入 lockfile 或新的外部依赖。
- 不在本变更中处理 viz 前端迁移/合并到 VSCode 插件（仅优化导出与运行期健壮性）。

## Decisions

### 1) JSONL 写出采用“单写者”模型（queue/worker 或等价 capture+replay）

对 `VizEventEmitter` 的并发写出，采用 single writer 作为默认实现边界：

- 多线程调用 `emit()` 时，MUST 不直接在多个线程中对同一个文件句柄写入；
- 写出动作集中到一个写者路径（例如后台 worker 线程 + queue，或集中 flush 阶段的 capture+replay）；
- 写者路径 MUST 保证每条事件写入是“行级原子”（至少在进程内并发下不产生半行交错）。

实现层选择（优先顺序）：

1. **单写者 worker（推荐）**：`emit()` 将序列化后的 JSON 行放入线程安全队列，后台写者线程串行写入文件；
2. **capture+replay**：将事件先捕获到内存结构，按确定顺序在单线程 flush（适用于 workflow 并发模式的回放边界）。

### 2) flush 策略保持可控，优先保留既有语义再做优化

当前每条事件 `flush()` 保证文件对 tail/回放尽快可见，但有性能成本。迁移到 single writer 后：

- 默认策略 SHOULD 先保持与现有语义一致（确保回归风险低）；
- 在不破坏“可解析性”契约的前提下，可引入可控的批量 flush（例如按条数/时间触发）作为后续优化点。

### 3) snapshot 保持 temp+replace 原子写策略不变

`viz_snapshot.json` 继续使用 temp+replace（已满足并发下可解析性契约），本变更不改其对外行为，仅确保与 JSONL 的写出边界相互独立且不会引入额外锁热点。

## Risks / Trade-offs

- **写者线程生命周期复杂度** → 通过显式 `close()`、超时 join、以及测试覆盖（并发写入 + 关闭时 drain）降低风险。
- **行为回归（写入可见性/时序）** → 先保持 flush 语义，必要时以可选策略渐进优化；以现有并发回归测试兜底。
- **queue 无界增长风险** → 在设计中明确背压策略（maxsize/丢弃/阻塞）并选择可验证的默认值。

