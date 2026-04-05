# yaml-dsl-schema (delta) Specification

## ADDED Requirements

### Requirement: kind-based `if/then` constraints MUST NOT trigger when `kind` is missing
系统 MUST 生成 JSON schema，使得所有基于 `kind` 分支的 `if/then` 约束在 `kind` 缺失时不触发。

动机：

- 编辑器侧的 YAML schema 校验不会展开 `$import`，因此允许存在 `{ $import: ... }` 形态的 mapping（此时 `kind` 通常在 fragment 内声明）。
- JSON schema 的 `properties.kind.const` 在 `kind` 缺失时不会失败，若不额外约束会导致 `then` 被错误触发，产生假阳性（例如误报 `resources.books.*.budget` 缺失）。

约束：

- 当 `if` 用于匹配 `properties.kind.const`（或等价模式）时，`if` MUST 同时包含 `required: ["kind"]`。
- 此要求至少 MUST 覆盖 `definitions.book`（`xlsx_file/xlsx_memory` 分支），并扩展到其它同类的 kind-variant 生成模式（若存在）。

#### Scenario: schema validates `$import`-based book mapping without false positives
- **GIVEN** demand YAML 中 `resources.books.report` 使用 `{ $import: fragments.report_book, path: {...} }`
- **AND** `fragments.report_book` 的 fragment mapping 内声明 `kind: xlsx_file`
- **WHEN** VSCode YAML schema（不展开 `$import`）对主 YAML 进行校验
- **THEN** MUST NOT 报告 `Missing property budget`（或其它 kind 分支误触发的假阳性）

