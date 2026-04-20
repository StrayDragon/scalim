## Why

当某个 ref loader 的 `lookup_keys` 规模很大时，框架当前支持通过 `lookup_chunk_size` 将一次 `LoadRef(keys)` 拆成多次 loader 调用并合并结果，以避免超长 `IN (...)` 或超大 payload。

但在 IO/RTT 主导的数据库访问场景中，“分片但串行”仍可能带来明显的 wall time 放大：例如一次批次内单个 source 需要拆成 5~20 次查询，每次都承担连接池等待、网络 RTT 与 SQL 解析的固定成本。此时即便 workflow 层不做并发调度，单个 source 的分片加载也可能成为批次瓶颈。

因此需要一个可维护、可控的方式：在保持语义一致的前提下，让 `lookup_chunk_size` 的分片 loader 调用 **可选并行**，以减少单批次的 I/O 等待时间。

## What Changes

- 系统将为 `lookup_chunk_size` 的分片加载路径引入“可选并行”能力：
  - 在明确的 opt-in 配置下，同一批次内、同一 `LoadRef(keys)` step 的多个 chunk loader 调用可并发执行（线程并发），并在合并阶段保证结果与串行分片语义等价。
  - 默认保持现状：未启用 opt-in 时，分片加载仍按串行执行。
- 系统将补齐可观测性与护栏：
  - 对每个 chunk 仍能发出 `loader_call` 事件（含 `lookup_key_count`），便于诊断并发带来的收益/成本。
  - 并发上限必须可控（避免隐式把 DB 压力放大为“默认行为”）。

## Capabilities

### New Capabilities
- `refloader-chunk-parallelism`: 定义 `lookup_chunk_size` 分片加载的并发语义、合并规则、观测与限流边界。

### Modified Capabilities
- (none)

## Impact

- **代码影响面**：`src/scalim/execution/executor/operators/load_ref/loader.py`（`lookup_chunk_size` 分片加载与合并路径）
- **性能与资源**：并发 chunk 会增加同一批次内的并行 DB 请求数；必须通过显式上限与可观测指标控制风险。
- **兼容性**：默认行为不变；仅在 opt-in 时改变执行策略。
