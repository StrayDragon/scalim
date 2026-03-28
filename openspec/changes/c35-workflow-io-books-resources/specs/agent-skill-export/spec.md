## MODIFIED Requirements

### Requirement: Generated References Cover Workflow YAML
系统 MUST 扩展 `scalim-yaml-dsl` skill 生成器,使受控生成 references 覆盖 workflow YAML 的语法与工具入口,并保持“schema/CLI/spec 为唯一真相”的导出策略.

至少 MUST 满足:

- 生成器 MUST 将 `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 视为 workflow YAML 的 canonical schema 输入,并将其纳入构建清单输入哈希.
- `references/syntax-catalog.gen.md` MUST 包含 workflow YAML 的语法索引,至少覆盖:
  - `workflow.runs[*]` 的关键字段: `id`、`demand`、`depends_on`、`init_vars`、`main_rows_from`
  - `workflow.options` 的关键字段: `max_concurrency`、`failure_policy`、`cache_pool`、`ctx`
  - `workflow.resources` 的关键字段: `books`
- `references/generated/cli-lsp-reference.gen.md` MUST 提供 workflow YAML 的可复制命令入口,至少包含:
  - 仓库内 workflow schema-only 校验命令（显式 `--schema .../workflow.gen.json`）
  - `yaml-dsl upsert-lsp-comment --type workflow` 的指引

#### Scenario: generated syntax catalog 包含 workflow 语法索引
- **WHEN** 维护者运行 `just gen-agent-skill`
- **THEN** `references/syntax-catalog.gen.md` 中必须可检索到 workflow YAML 的字段索引
- **THEN** 且其中必须包含 `depends_on/init_vars/main_rows_from/resources/books/ctx` 等关键字段名

#### Scenario: generated CLI/LSP reference 包含 workflow 命令入口
- **WHEN** 维护者运行 `just gen-agent-skill`
- **THEN** `references/generated/cli-lsp-reference.gen.md` 必须包含 workflow schema-only 校验命令示例
- **THEN** 且必须包含 `upsert-lsp-comment --type workflow` 的命令示例

