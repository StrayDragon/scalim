## ADDED Requirements

### Requirement: `scalim-yaml-dsl` skill explains when to use `normalize`
系统 MUST 更新 `artifacts/skills/scalim-yaml-dsl/**`,使其能区分:
- 需要先把整个 source 返回值 reshape 成 `key -> row` 的场景: 优先使用 `normalize`
- 只是当前 row value 内部字段嵌套: 优先使用字段级 `extract`

#### Scenario: list-returning loader 优先推荐 `normalize`
- **WHEN** 用户给出的 lookup source loader 返回 `list[row]`,而不是 `key -> row` 映射
- **THEN** skill MUST 优先给出 `normalize.kind=index_by_key` 的方案
- **AND** MUST NOT 默认建议为此仅写一个 Python wrapper

#### Scenario: 仅字段嵌套时不误导到 `normalize`
- **WHEN** 用户的 source loader 已经返回 `key -> row`,只是 row 内部字段有嵌套
- **THEN** skill MUST 优先推荐字段级 `extract`
- **AND** MUST 明确说明此时不需要 source-level `normalize`
