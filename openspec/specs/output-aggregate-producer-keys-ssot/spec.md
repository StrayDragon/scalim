# output-aggregate-producer-keys-ssot Specification

## Purpose
TBD - created by archiving change c45-output-aggregate-producer-keys-ssot. Update Purpose after archive.
## Requirements
### Requirement: aggregate producer key enums MUST be centralized and shared
系统 MUST 为 aggregate 输出相关的 producer keys 提供一个 SSOT（单一事实来源）模块，并要求以下层级共享同一份枚举集合：

- YAML 解析与语义校验（outputs parser）
- 运行时装配（output composition YAML）
- 工具/自省（introspection）
- YAML JSON Schema（canonical `demand.gen.json` 的生成源）
- 前端 editor schema bundle（用于补全/hover/schema validate）

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

#### Scenario: load_output_config default aggregate output_fields matches runtime default (includes compute)
- **GIVEN** YAML primary output has `aggregate.fields` that includes at least one `compute` post field
- **AND** YAML does not explicitly specify `outputs.*.fields`
- **WHEN** 调用 introspection `load_output_config()`
- **THEN** 返回的默认 `output_fields` MUST 包含该 `compute` 字段
- **AND** 默认 `output_fields` MUST 与 runtime 的默认 aggregate 输出列选择一致（避免工具/运行时漂移）

#### Scenario: JSON schema + editor bundles include the same producer keys as SSOT
- **WHEN** 系统在 `schema_dsl/models/outputs.py` 中生成 canonical `demand.gen.json`（或等价 schema）
- **THEN** schema 中 aggregate producer keys 的可选集合 MUST 与 SSOT 一致（不得缺 key / 多 key）
- **AND** 前端 editor 使用的 schema bundle MUST 与 canonical schema 同步（避免 editor 漂移）

