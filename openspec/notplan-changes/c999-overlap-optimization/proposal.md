## Why
**FR024: 重叠计算内存优化**

处理主数据分区时,如果有一个关联字段需要走关联函数逻辑计算结果关联,此时上一个分区和下一个分区的关联字段集合可能有重叠,需要重叠计算优化内存占用.

### 需求背景

比如订单表 left join 用户信息表时,对于每个分区都可以计算出一个 user_ids 去重集合.第一个区块 A 的用户 id 集合可能是 {1,2,3,4,5},第二个区块 B 可能是 {1,3,4,8}... 这里有重叠,需要优化处理.

讨论后的方案:暂时不处理.当前实现尚未覆盖该优化,需要先固化规范以便后续实施.

## What Changes
- 增补 overlap-optimization 规范增量,定义重叠键复用与缓存边界.
- 添加最小设计说明以列出待决策项.

## Impact
- 受影响的规范: `openspec/specs/overlap-optimization/spec.md`
- 受影响的代码: `src/scalim/execution/*` (计划性变更)

## Process Control
- 变更进入调研阶段即视为开始实施
- 完成调研后必须先停下来报告并请求 review 意见,未获确认不得继续实现

## Calibration Notes (2026-03-25)

- 主规范 `openspec/specs/overlap-optimization/spec.md` 已存在,标记"📋 待实现",明确记录"批次间不复用关联结果"为当前行为
- `PreloadCache`（`src/scalim/execution/preload_cache.py`）已有完善的 inflight dedup/signature guardrail/wait diagnostics,但仅服务于 preload 场景,不涉及跨批次 load_ref 结果复用
- `AdaptiveLoadRefScheduler`（`src/scalim/execution/adaptive/loadref_scheduler.py`）是实际调度 load_ref 的核心,如要实现重叠优化需要在此层引入跨批次缓存窗口
- 已将 `PROJECT_DIST_NAME` 占位符替换为实际路径
