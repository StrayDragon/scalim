## Context

当前 `resources.books.*` 的 authoring surface 中:

- `books.kind=xlsx_memory` 强制要求用户显式提供 `budget.max_sheets/max_total_cells`。
- `books.*.write_defaults.mode` 默认值为 `append`。

在实际使用中,用户经常会为了绕过预算限制而把 `budget.*` 设成极大值,并在多个 book 上重复声明 `write_defaults.mode: sheet`。这使得:

- YAML 变得冗长,并且“用极大值表达无限制”不直观。
- 默认行为与常见用法不一致,导致额外样板配置。

同时,本仓库文档/生成物存在严格治理边界:

- `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json` 等 `*.gen.*` 为生成物,禁止手改。
- `docs/doc/yaml-dsl/schema-reference.gen.md` 为生成物/注入文档,必须通过 `just gen-docs` 刷新。

## Goals / Non-Goals

**Goals:**

- 允许 `books.kind=xlsx_memory` 省略 `budget`(减少样板配置)。
- 当 `budget` 省略时,视为**无限制**(不启用预算护栏),与用户目前“写极大值”效果等价,但表达更清晰。
- 将 `books.*.write_defaults.mode` 默认值调整为 `sheet`,减少重复配置。
- 同步更新 schema 生成、文档生成与测试覆盖,保证 drift gates 通过。

**Non-Goals:**

- 不引入新的 YAML 入口(例如 `books_defaults`/全局 preset)。
- 不改动 `xlsx_memory` 的 typed internal rows / align_by 约束等既有语义。
- 不在本变更中重做输出层的整体写入策略/接口拆分。

## Decisions

1) `xlsx_memory.budget` 省略语义

- 选择: **省略 budget == unlimited**。
- 理由:
  - 与用户现有“写极大值”等价,不会引入新的隐式限制导致意外 fail-fast。
  - 实现成本低: 允许 `budget` 缺省并在运行时将 `<=0` 视为“无限制”即可。
- 备选方案:
  - A) 省略 budget 使用“默认预算护栏”(有限值)。优点是更安全,但会改变“省略时能跑大数据”的预期,并且仍可能促使用户继续写极大值绕过。
  - B) 引入 `budget: {unlimited: true}` 明确关闭护栏。更显式但仍需要额外配置,不符合“减少样板”的目标。

2) “无限制”在 IR/runtime 中的表达

- 选择: 仍沿用现有 `budget.max_*` 字段,并约定当值 `<=0` 时不做预算检查。
- 理由:
  - 避免引入 `Optional[int]` 的跨层类型改造。
  - `build_workflow_resource_defs` 当前对缺失字段会落到 `0`,天然可复用。

3) `write_defaults.mode` 默认值调整

- 选择: 将 `DEFAULT_BOOK_WRITE_MODE` 从 `append` 调整为 `sheet`。
- 理由:
  - 减少用户在典型报表场景下的重复声明。
  - 让“一个 output 对应一个 sheet(覆盖写)”成为默认直觉。
- 备选方案:
  - A) 保持默认 `append`,仅文档推荐 `sheet`。不能解决样板 YAML 的核心问题。
  - B) 仅对 `xlsx_file` 改默认,对 `xlsx_memory` 保持不变。会增加认知分叉,且用户示例两种都在显式设置 `sheet`。

4) 生成边界与 drift gate

- schema: 通过修改 `schema_dsl` 的 SSOT(模型/枚举默认值)后运行 `just gen-yaml-dsl-schema` 生成 `*.gen.*`。
- docs: 通过更新 SSOT 文档并运行 `just gen-docs` 刷新 injected blocks/`*.gen.md`。
- OpenSpec: 提交前运行 `just openspec-check` 确保 sanitize + validate 通过。

## Risks / Trade-offs

- [风险] 省略 `budget` 会允许极端数据量写入,可能导致更晚暴露的内存问题 → [缓解] 通过文档强调: 需要护栏时应显式配置 `budget`,并在预算超限错误中提示如何开启预算。
- [风险] 默认 `write_defaults.mode` 从 `append` 改为 `sheet` 是破坏性变更,会改变未显式设置 mode 的旧 YAML 行为 → [缓解] 在 release notes/迁移提示中明确,并在测试中覆盖典型回归用例。

