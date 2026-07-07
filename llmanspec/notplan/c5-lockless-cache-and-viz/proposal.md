## Why

在服务端/高并发场景下，除了 workflow 输出发布（B/D）之外，运行时仍有两类“锁热点”会显著增加推理成本与尾延迟风险：

- **组 A**：缓存/池（`PreloadCache`、`workflow cache_pool`）的并发协调依赖 `threading.Lock` 与 inflight 等待，锁粒度与状态机复杂，容易放大 contention。
- **组 C**：可视化/可观测性输出（viz JSONL / snapshot）的写出路径仍有并发写入与序列化需求，当前实现包含额外锁与 IO 交错风险点。

我们希望在不破坏对外语义的前提下，将这两块的并发协调进一步“去锁化/少锁化”，让实现更干净、更容易维护与验证。

## What Changes

- 组 A（cache/pool）：
  - 收敛并发协调模型：统一 singleflight/inflight 的状态机与诊断字段，减少分散实现与重复逻辑。
  - 降低锁竞争：尽量减少全局锁/大临界区，保证 `load_fn` 等外部回调永远不在锁内执行，并将锁持有时间压缩到“仅保护内部状态一致性”的范围。
  - 增强可诊断性：在等待/冲突/淘汰等关键路径提供稳定的诊断信号，便于在服务端定位 contention 与热点 source_id。

- 组 C（viz/observability 输出）：
  - 收敛“写出串行化”边界：尽量将文件写出集中到单写者（或等价的 capture+replay/flush）路径，减少对显式锁的依赖。
  - 明确并发下文件完整性：确保 snapshot 与 JSONL 事件流在并发/重入下始终可解析（不产生半写/损坏文件）；必要时采用原子写入策略与更稳健的 append 方案。
  - 保持输出目录干净：不引入 lockfile；仅在框架约定的自管目录下生成 viz 输出与元数据（已有 `scalim-viz/<run_id>/...` 约定继续沿用）。

> 本 change 为 “proposal-only” 占位，用于记录 A/C 的目标与契约边界；后续实现将以独立 design/specs/tasks 继续推进。

## Capabilities

### New Capabilities
- （无；优先通过修改既有 capabilities 的要求来收敛契约与实现边界）

### Modified Capabilities
- `preload-cache-inflight-dedupe`: 进一步收敛并发协调与锁边界（更小临界区、外部回调不在锁内、诊断字段更稳定）。
- `workflow-cache-pool`: 强化并发 `get_or_load` 的 singleflight 与“锁外回调/锁外 emit”护栏，并降低锁竞争。
- `observer-concurrency-contract`: 明确默认并发语义下 observers 不需要自行线程安全即可正确工作，并为文件型输出提供更清晰的串行化保障。
- `flow-visualization`: 强化 viz snapshot 与 JSONL 事件流在并发/重入下的可解析性与原子性约束（不依赖 lockfile）。

## Impact

- 受影响代码（预期）：
  - `src/scalim/execution/preload_cache.py`
  - `src/scalim/execution/workflow_cache_pool.py`
  - `src/scalim/ob/manager.py`（如需调整回调串行化边界）
  - `src/scalim/ob/presets/_internal/viz_output.py`
  - 相关测试与基准（用于验证锁竞争下降与回归）

- 受影响行为：
  - 对外配置面尽量保持不变（目标为内部并发协调与 IO 健壮性的改进）。
  - 性能与稳定性预期提升：减少锁竞争、减少并发写出导致的文件损坏/半写风险、诊断更可操作。

