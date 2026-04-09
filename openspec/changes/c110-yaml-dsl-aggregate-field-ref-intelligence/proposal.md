## Why

当前 YAML DSL 的 LSP 已经覆盖了 imports/$import、outputs[*].fields、表达式字段引用、以及部分实体跳转，但在 `outputs[*].aggregate` 相关结构里仍缺少同等级的“字段智能”(completion/hover/definition)。这会让写 aggregate 报表时字段选择与重构成本显著升高，且容易出现“字段拼写/引用位置不一致”类错误。

## What Changes

- 在 `outputs[*].aggregate` 相关路径下补齐“字段引用”的 completion/hover/definition（含空值/空 list item），覆盖至少：
  - `aggregate.group_by`（field_id list；支持复合 key：`group_by[*][*]`）
  - `aggregate.fields.*.*.field`（单 field_id）
  - `aggregate.fields.*.*.fields[*]`（复合 fields 列表）
  - `aggregate.fields.*.(row_number|rank|dense_rank).by`（优先 out_field_id；其次 group_by；最后全局 field_id）
  - `aggregate.fields.*.(row_number|rank|dense_rank).partition_by[*]`（语义上要求为 group_by 子集，但 completion 允许显示全局 field_id 作为低优先 fallback 并标注）
  - `aggregate.fields.*.(row_number|rank|dense_rank).order_by[*]`（同 by）
  - `aggregate.fields.*.score_by_rank.rank_field`（引用 out_field_id；同样提供全局 fallback 以方便跳转）
- completion 候选分层（稳定排序 + 标注）：
  1) `aggregate.fields` 的 out_field_id（最高优先）
  2) `group_by` 引用的 field_id（次优先）
  3) 全局可见 field_id（低优先、明确标注；用于方便用户跳转/重构）
- go-to-definition 支持多 locations：当 token 同时命中 out_field_id 与全局 field_id 时，**aggregate 内定义点必须排第一**，其余候选稳定排序+去重。
- 保持性能：不引入每字符全量重算；复用现有 debounce/缓存策略；completion 仍以 Ctrl+Space 为主。
- 增加回归测试与示例覆盖，确保 notebooks/demo 里的典型 aggregate YAML 可验证。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `yaml-dsl-lsp-server`: 扩展字段智能覆盖范围到 aggregate/rank 等输出结构。
- `yaml-dsl-lsp-notebooks-regression`: 增加 aggregate 相关用例的回归验证点。

## Impact

- 主要影响 `packages/scalim-yaml-dsl-lsp/` 的 cursor extraction、completion/definition/hover 逻辑与对应测试。
- 可能需要补充/更新 editor integration 的验证 checklist（不涉及 runtime 行为变更）。
