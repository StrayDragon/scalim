## Context
- 目标: 减少主数据分区之间关联字段集合重叠导致的重复 loader 调用与内存占用.
- 当前: 批次之间不共享 ref loader 结果.

## Goals / Non-Goals
- Goals: 跨批次复用关联结果以降低重复加载与计算.
- Non-Goals: 不改变 preload_forever 的既有语义.

## Decisions
- Decision: 在执行期引入跨批次的可选短期缓存 (窗口/容量可配).
- Alternatives considered: 全局缓存 (风险过高,内存不受控).

## Risks / Trade-offs
- 缓存命中率不足 -> 引入额外内存但收益有限.
- 缓存一致性 -> 与数据源变更的可见性需说明.

## Migration Plan
- 先引入只读缓存层,默认关闭.
- 根据真实 workload 再调整默认策略.

## Open Questions
- 缓存粒度: 按 source 还是按 lookup key?
- 清理策略: LRU/TTL/固定窗口?
- 需要暴露哪些指标以评估效果?

## Research Summary (post-discovery)
- 现状缓存分层:
  - `preload_forever`: 预加载结果存放在 runtime 的 `preloaded_cache`,跨批次复用(但只覆盖显式 preload 模式).
  - `load_ref_cache`: 当前仅“批次级”缓存,每个 batch 开始会清空(窗口=1 batch),无法覆盖跨批次重叠键.
- 缺口: 对非 preload 的 ref loader,当相邻批次 lookup key 集合高度重叠时,会重复调用 loader 并重复持有中间结果,产生可优化的 CPU/IO/内存开销.
- 候选插入点: 在执行期引入“跨批次短期缓存”(窗口/容量可配),其生命周期应独立于 `load_ref_cache` 的 batch reset,但必须显式可控并默认关闭.

## Reference Examples

### Example: 相邻批次 lookup_keys 重叠
```text
batch A: lookup_keys = {1,2,3,4,5}
batch B: lookup_keys = {1,3,4,8}

期望:
- batch B 对 {1,3,4} 直接命中复用缓存
- 仅对 {8} 触发 loader 调用
```

### Example: 缓存窗口/容量(伪配置,用于说明语义)
```yaml
execution:
  overlap_cache:
    enabled: true
    window_batches: 2   # 仅保留最近 N 个 batch 的条目(或等价语义)
    max_entries: 20000  # 容量上限
    eviction: lru       # 淘汰策略示意
```

### Example: 建议暴露的观测指标(用于评估收益)
```text
overlap_cache.hit_count
overlap_cache.miss_count
overlap_cache.hit_rate
overlap_cache.entries
overlap_cache.evictions
overlap_cache.estimated_bytes (可选,粗略估计即可)
```
