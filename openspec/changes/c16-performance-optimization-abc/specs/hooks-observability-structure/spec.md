# hooks-observability-structure Specification

## ADDED Requirements

### Requirement: High-cardinality diagnostics MUST be wants-gated at the callsite
系统 MUST 对高基数诊断路径提供“调用点 wants-gated”语义：当 `InstrumentationHub.wants(event_type)=false` 时，执行层 MUST 不进行与数据规模成正比的诊断计算与中间结构构造（不仅仅是不构造 `Event` envelope）。

该要求适用于但不限于：
- `relation_lookup`（逐行命中/缺失诊断）
- 其它可能出现 `O(row_count)` 或 `O(key_count)` 的诊断/观测辅助逻辑

#### Scenario: relation lookup hit/miss diagnostics are skipped when not wanted
- **WHEN** `InstrumentationHub.wants("relation_lookup")=false` 且执行一次包含关联加载的批次
- **THEN** 系统 MUST 不执行逐行 hit/miss 分类诊断逻辑

#### Scenario: relation lookup diagnostics still work when wanted
- **WHEN** `InstrumentationHub.wants("relation_lookup")=true` 且执行一次包含关联加载的批次
- **THEN** 系统 MUST 继续发出 `relation_lookup` 事件并保持既有 payload 结构

