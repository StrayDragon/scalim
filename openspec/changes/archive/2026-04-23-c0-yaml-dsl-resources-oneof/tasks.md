## 1. Schema SSOT + Generated JSON Schema

- [x] 1.1 更新 schema SSOT `src/scalim/dsl/yaml_dsl/schema_dsl/models/resources.py`：将 `resources.books.*` / `resources.files.*` 升级为 oneOf 分支对象（`xlsx_file` / `xlsx_memory`；`csv_file`），并保留 `write_defaults` 作为分支外公共字段；将 `encoding` 收敛到 `resources.files.*.csv_file.encoding`；demand schema 支持 `$import`-only 与 `$import + override`（node/branch），workflow schema 不暴露 `$import`
- [x] 1.2 刷新生成物 `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`、`src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`（生成入口：`just gen-yaml-dsl-schema`；禁止手工编辑）
- [x] 1.3 运行 drift gate：`just schema-drift-check`（确保 SSOT→生成物一致）

## 2. Demand 解析与校验（Python 3.6 boundary）

- [x] 2.1 更新 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/loader.py`：解析 books/files 的 oneOf 分支写法并推导内部 `kind`（含 `resources.files.*.csv_file.encoding`）；对 legacy `kind` 写法 fail-fast 并给出可复制迁移提示
- [x] 2.2 更新 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/validator.py`：将资源路径语义校验与 init_var mapping 校验迁移到新路径（例如 `resources.files.*.csv_file.path`、`resources.books.*.xlsx_file.path`、`resources.books.*.xlsx_memory.export_xlsx.path`），并确保诊断 path 与迁移提示指向新 authoring surface
- [x] 2.3 为资源解析/校验补充最小回归测试（若已有 pytest 基建）：覆盖 books/files 两类资源、旧写法迁移提示、demand `$import`（node/branch、以及 `$import + override`）展开后的行为不变

## 3. Workflow 解析与合并（imports 禁止）

- [x] 3.1 更新 `src/scalim/dsl/yaml_dsl/workflow_config/_parse.py`：解析 books/files 的 oneOf 分支写法；继续在 workflow resources 下 fail-fast 拒绝 `imports/$import`；对 legacy `kind` 写法给出迁移提示
- [x] 3.2 回归 merge/override 与 patch 诊断：确保 demand/workflow/overrides precedence 不变，且 unknown keys / 类型不匹配错误的 path 仍稳定可定位

## 4. Docs / Examples / Skills

- [x] 4.1 更新 `docs/doc/yaml-dsl/user-guide.md`：把 resources.books/files 示例迁移为 oneOf 分支写法
- [x] 4.2 更新示例与技能参考：`agentdev/skills/scalim-yaml-dsl/references/**`、fixtures/notebooks 中的 YAML（如有）
- [x] 4.3 若涉及 docs 注入区块或生成页：运行 `just gen-docs`，并用 `just docs-drift-check` / `just generated-artifacts-drift-check` 验证无 drift

## 5. QA / Gates

- [x] 5.1 运行 Python 3.6 兼容性门禁：`just py36-compat-check` + `just py36-typingext-check`
- [x] 5.2 运行质量门禁：`just qa`
- [x] 5.3 运行 OpenSpec 校验：`just openspec-check`（或 `openspec validate --all --strict --no-interactive`）
