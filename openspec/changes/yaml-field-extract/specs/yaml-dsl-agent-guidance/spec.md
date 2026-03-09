## ADDED Requirements

### Requirement: `scalim-yaml-dsl` skill guides field-level `extract` usage
系统 MUST 更新 `artifacts/skills/scalim-yaml-dsl/**`,使其在“loader 返回嵌套 row value”场景下优先推荐字段级 `extract`,而不是先建议编写 Python wrapper。

skill 文档 MUST 至少说明:
- `extract` 相对当前 key 对应的 row value 解析
- `field` 仍是 raw flat selector
- 只有 whole-result reshape 才应考虑 source-level `normalize` 或 wrapper

#### Scenario: 嵌套 row value 场景优先推荐 `extract`
- **WHEN** 用户给出的 source loader 已经能返回按 key 索引的 row value,只是字段值藏在嵌套 dict / 对象内
- **THEN** skill MUST 优先给出 `extract` 写法
- **AND** MUST NOT 默认建议再包一层 Python flatten wrapper
