## ADDED Requirements

### Requirement: `scalim-yaml-dsl` skill guides field-level `extract` usage
系统 MUST 更新 `artifacts/skills/scalim-yaml-dsl/**`,使其在“loader 返回嵌套 row value”场景下优先推荐字段级 `extract`,而不是先建议编写 Python 包装函数。

skill 文档 MUST 至少说明:
- `extract` 相对当前 key 对应的 row value 解析
- `extract` 是唯一字段取值写法(包含 rename 与 nested path)
- bracket 语法示例: `"[1].x"`、`'["a.b"]'`
- 只有需要整理整体结果形状时才应考虑源级 `normalize` 或包装函数

#### Scenario: 嵌套 row value 场景优先推荐 `extract`
- **WHEN** 用户给出的 source loader 已经能返回按 key 索引的 row value,只是字段值藏在嵌套 dict / 对象内
- **THEN** skill MUST 优先给出 `extract` 写法
- **AND** MUST NOT 默认建议再包一层 Python flatten 包装函数
