# output-aggregate-enums-ssot Specification

## Purpose
为 by_yaml 的 aggregate 输出 producer keys 枚举提供单一事实来源（SSOT），避免 parser/runtime/introspection 跨层重复定义导致的漂移。

## ADDED Requirements

### Requirement: aggregate producer key enums MUST be centralized and shared
系统 MUST 为 aggregate 输出相关的 producer keys 提供一个 SSOT（单一事实来源）模块，并要求以下层级共享同一份枚举集合：

- YAML 解析与语义校验（outputs parser）
- 运行时装配（output composition YAML）
- 工具/自省（introspection）

该 SSOT MUST 至少包含并可被上述模块引用：

- metric producer keys（例如 `count/sum/min/max/...`）
- rank producer keys（例如 `row_number/rank/dense_rank`）
- post producer keys（例如 `score_by_rank/call_by/compute` 等，按语义拆分）

#### Scenario: parser/runtime/introspection share the same enum sets
- **WHEN** 系统提供 `schema_dsl.output_enums`（或等价模块）作为 SSOT
- **THEN** outputs parser MUST 不再维护 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS` 的本地副本
- **AND** runtime output composition YAML MUST 不再维护 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS` 的本地副本
- **AND** introspection MUST 不再维护 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS` 的本地副本
- **AND** 三者在逻辑上 MUST 共享同一份枚举集合（允许工具层在 SSOT 基础上选择子集作为默认行为，但不得重新定义字符串集合）
