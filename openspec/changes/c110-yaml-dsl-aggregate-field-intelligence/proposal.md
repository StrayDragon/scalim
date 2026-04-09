## Why

当前 YAML DSL 的 LSP 已经覆盖了 imports/$import、outputs[*].fields、表达式字段引用、以及部分实体跳转，但在 `outputs[*].aggregate` 相关结构里仍缺少同等级的“字段智能”(completion/hover/definition)。这会让写 aggregate 报表时字段选择与重构成本显著升高，且容易出现“字段拼写/引用位置不一致”类错误。

## What Changes

- 在 `outputs[*].aggregate` 相关路径下补齐 field-id 的 completion/hover/definition，包括但不限于：
  - `aggregate.group_by`（list of field_id）
  - `aggregate.fields.*.<metric>.field`（单 field_id）
  - `aggregate.fields.*.<metric>.fields`（复合 fields 列表）
  - `aggregate.fields.*.rank.*.by`（field_id）
- 统一上述位置的光标抽取规则，保证 **Ctrl+Space** 在空值/空 list item 场景也可触发候选列表。
- 保持性能：不引入每字符全量重算；复用现有 debounce/缓存策略。
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
