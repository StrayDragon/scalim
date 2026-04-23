# yaml-dsl-lsp-hover Specification

## Purpose
为 `scalim-yaml-dsl-lsp` 提供一套可配置、可扩展且可在多编辑器中复用的 hover 输出规范：hover 内容以 Markdown card 形式呈现，并由 `scalim.yaml yaml_dsl.lsp.hover` 控制展示字段与顺序，从而在不与 schema hover 重复的前提下，为“引用类”写作面提供更高价值的上下文信息。

## Requirements

## ADDED Requirements

### Requirement: YAML DSL LSP hover MUST emit Markdown cards
系统 MUST 将 `scalim-yaml-dsl-lsp` 产生的 hover 响应以 `MarkupKind.Markdown` 返回（而非 PlainText），以便结构化展示（标题/章节/列表/表格）并提高可读性。

约束：

- hover 文本 MUST 为“稳定且确定”的 Markdown（同输入下输出一致，且不依赖外部网络/动态运行时状态）。
- hover 生成过程 MUST NOT 执行用户代码（仅允许文件系统读取与 AST 解析）。

#### Scenario: relation step field hover returns Markdown
- **GIVEN** demand YAML 的 `relations.*.steps[*].from/to` 中存在 `source.field_id` 引用
- **WHEN** 用户在 `field_id` token 上触发 hover
- **THEN** server 返回的 hover MUST 使用 `MarkupKind.Markdown`
- **AND** hover 内容 MUST 以“card”形式呈现（包含标题，并包含至少一个结构化区块，例如列表或章节）

### Requirement: LSP hover rendering MUST be configurable via `scalim.yaml yaml_dsl.lsp.hover`
系统 MUST 支持在 `scalim.yaml` 中通过 `yaml_dsl.lsp.hover` 配置 hover 的展示字段与顺序，并适用于常见 hover 类型（至少覆盖：field/entity/python/builtin/aggregate/call_by kwargs value）。

配置规则：

- `yaml_dsl.lsp.hover` MUST 为 mapping（对象）。
- 每个 hover 类型下的配置 MUST 为字符串数组；数组顺序 MUST 决定输出顺序。
- 当 `yaml_dsl.lsp.hover` 或某个子项缺失时，系统 MUST 应用稳定的默认字段列表。
- 当用户提供未知字段名时：
  - `scalim.yaml` 解析 MUST fail-fast（返回结构化错误；不得静默忽略）
  - `scalim.yaml` JSON Schema 校验 MUST 失败（schema-only fail-fast）

#### Scenario: hover config defaults are applied when absent
- **GIVEN** 项目存在 `scalim.yaml` 且未声明 `yaml_dsl.lsp.hover`
- **WHEN** 用户触发任意受支持的 DSL hover
- **THEN** hover MUST 使用默认字段列表渲染
- **AND** hover MUST NOT crash

#### Scenario: invalid hover field name is rejected
- **WHEN** 用户在 `scalim.yaml` 中配置 `yaml_dsl.lsp.hover.field_reference: [\"unknown_field\"]`
- **THEN** schema-only 校验 MUST 失败并指向该字段
- **AND** runtime 解析 `scalim.yaml` MUST 失败并返回可诊断错误信息

### Requirement: Hover content MUST avoid duplicating schema hover
系统 MUST 将 DSL hover 的内容面定位为“引用语义 + 上下文摘要”，并避免重复 YAML schema hover 已覆盖的信息（例如字段约束/枚举/类型说明等纯 schema 信息）。

#### Scenario: DSL hover focuses on resolved semantics
- **GIVEN** YAML schema hover 已能为 `relations.*.steps` 字段提供格式/语义说明
- **WHEN** 用户在 `source.field_id` 的 token 上触发 DSL hover
- **THEN** DSL hover MUST 优先呈现解析后的语义信息（例如 source/field 的声明位置、配置摘要或推断结果）
- **AND** MUST NOT 仅重复 schema 中对格式的描述
