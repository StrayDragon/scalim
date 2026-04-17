## Why

目前用户在编写 `workflow.resources.books` 时,经常会为了“跑起来”而重复粘贴以下配置:

- `books.<id>.budget.max_sheets/max_total_cells` 填一个极大值(本质是在关闭预算护栏)
- `books.<id>.write_defaults.mode: sheet` 在多个 book 上重复出现

这会导致 YAML 噪音增多、学习成本上升,而且“用极大值模拟无限制”也让预算语义变得不清晰。

## What Changes

- `books.kind=xlsx_memory`:
  - `budget` 变为可选项；当省略时,系统使用运行时默认预算(作为护栏)。
  - 当用户显式提供 `budget` 时,仍按既有语义生效。
- `books.*.write_defaults`:
  - **BREAKING**: `write_defaults.mode` 的默认值从 `append` 调整为 `sheet`(更贴近大多数“按 output 写成一个 sheet”的使用方式)。
- 同步更新:
  - YAML schema 生成物与 schema-reference 文档(受控生成)。
  - 解析/编译期的诊断信息,确保在命中默认预算护栏时能提示用户如何显式配置预算。
  - 覆盖/回归测试与示例文档。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `yaml-dsl-books-resources`: 调整 `xlsx_memory.budget` 的必填约束为“可选 + 默认值”,并调整 `write_defaults.mode` 默认值。

## Impact

- 影响 YAML authoring surface: `resources.books.*`(demand/workflow)。
- 影响运行时行为:
  - 省略 `xlsx_memory.budget` 时会引入默认预算护栏(不再需要用极大值关闭限制)。
  - 未显式设置 `write_defaults.mode` 的配置将从 `append` 变为 `sheet`(破坏性变更,需在变更说明中强调)。
- 影响受控生成物:
  - `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json` 等 schema 生成物
  - `docs/doc/yaml-dsl/schema-reference.gen.md` 等文档生成物

