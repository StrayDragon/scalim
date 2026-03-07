# overlap-optimization Specification

**状态: 📋 待实现** - 当前方案为暂不处理,跨批次复用缓存待实现

## Purpose
当前实现不提供跨批次的关联结果复用,除 preload_forever 外每个批次独立加载并在执行时重算;该状态与 ExecutionRuntime 仅持有预加载缓存的行为一致.

## Context
**FR024: 重叠计算内存优化**

处理主数据分区时,相邻分区的关联字段集合可能有重叠(如区块 A 的 user_ids={1,2,3,4,5},区块 B 的 user_ids={1,3,4,8}),需要重叠计算优化内存占用.

当前方案:暂时不处理.当前实现未引入跨批次复用缓存.
## Related Code (as implemented)
- `src/IMPL_ROOT/execution/executor/runtime/runtime.py` (`preloaded_cache` vs per-batch `load_ref_cache`)
- `src/IMPL_ROOT/execution/pipeline/base/pipeline.py` (`preload_forever` preloading + per-batch cache reset)
- `src/IMPL_ROOT/execution/executor/operators/load_ref/loader.py` (preloaded cache fast-path)

## Requirements
### Requirement: 批次间不复用关联结果
系统 SHALL 在每个批次内独立执行关联加载,除 preload_forever 缓存外不复用上一批次结果.

#### Scenario: 相邻批次键重叠
- **WHEN** 相邻批次存在重叠的关联键集合
- **THEN** 系统仍应在该批次内独立执行关联加载(除预加载缓存外)

## Notes
- 未提供可配置的重叠窗口或缓存淘汰策略.
