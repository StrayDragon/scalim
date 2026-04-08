## ADDED Requirements

### Requirement: expression identifier tokens MUST be resolvable to field definitions

在 `compute`/`where` 等安全表达式字符串内,当光标位于某个 identifier token 上时,semantics core MUST 能静态解析该 token 并用于 editor 语义能力:

- semantics core MUST 能抽取该 token 的精确 range（仅覆盖 token）。
- semantics core MUST 能将 token 解析为字段引用（在当前上下文作用域内），用于 hover/definition/completion。

#### Scenario: compute expression token resolves to field definition
- **GIVEN** YAML 声明 `fields.a: ...` 且存在 `fields.sum.compute: \"a + 1\"`
- **WHEN** 光标位于表达式中的 token `a` 上并触发 definition/hover
- **THEN** token MUST 解析为对 `fields.a` 的引用
- **AND** definition MUST 指向 `fields.a` 的声明位置
