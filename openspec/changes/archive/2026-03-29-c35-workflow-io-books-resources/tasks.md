## 1. Canonical Schema + Models (SSOT)

- [x] 1.1 在 `src/scalim/dsl/by_yaml/schema_dsl/models/` 增加 demand 侧 `resources.books`/`outputs_defaults.to.book`/`outputs[*].to`/`outputs[*].write` 的 schema_dsl 模型,并确保 `additionalProperties=false` 与 enum/default 口径与本 change specs 一致。
- [x] 1.2 在 `src/scalim/dsl/by_yaml/schema_dsl/` 增加 workflow 侧 `workflow.resources.books` 的 schema_dsl 模型,并在 schema-only 校验阶段拒绝 `workflow.runs[*].writes` 与 `workflow.resources.workbooks/csvs/sheetbooks`。
- [x] 1.3 破坏性收敛输出 authoring surface：在 demand schema-only 与 runtime semantic 校验阶段拒绝 `outputs[*].container.type=workbook` 与 `container.path: ""`(pathless csv),并将 `.xlsx` 输出统一迁移到 books 绑定。
- [x] 1.4 更新生成物并通过漂移门禁：
  - 运行 `just gen-yaml-dsl-schema`
  - 运行 `just schema-drift-check`（确保 `src/scalim/dsl/by_yaml/schema/*.gen.json` 无 drift）

## 2. Demand 编译：books 解析 + 输出绑定（standalone 可运行）

- [x] 2.1 在 demand compile/run 管线中实现 outputs→book binding 解析：支持 `outputs_defaults.to.book` 继承、`outputs[*].to.book` 覆盖、默认 `sheet=output.name`、并在编译期做 Excel sheet 名校验(<=31 + 禁止 `\\ / ? * [ ] :`)。
- [x] 2.2 实现 `resources.books.*.kind` 分支校验：`xlsx_file` 必须有 `path`; `xlsx_memory` 必须有 `budget` 且可选 `export_xlsx`。
- [x] 2.3 实现 standalone fail-fast：当 outputs 绑定到缺失的 `book_id` 时,`compile/run` 必须 fail-fast 且错误信息包含缺失 book_id 与迁移提示（在 demand 声明资源 / 在 workflow 声明资源 / 或在 Python overrides 提供）。
- [x] 2.4 `.xlsx` 输出路径注入收敛：将旧的 `outputs[*].container.path: {$init_var: ...}`(workbook container) 动态注入迁移到 `resources.books.*.path` / `export_xlsx.path` 并保持同样的错误定位(`init_vars` 缺失时指向具体 path 节点)；`csv` 输出仍可继续使用 `outputs[*].container.path: {$init_var: ...}`(但不允许 `path: \"\"`)。

## 3. Workflow 编译：移除 `writes`，从 demand 输出绑定推导内部写入节点

- [x] 3.1 移除 workflow YAML 的 `runs[*].writes` 解析、校验与 schema；更新 `src/scalim/dsl/by_yaml/workflow_config.py` 与 `src/scalim/dsl/by_yaml/workflow_compile.py` 的相关逻辑与错误文案。
- [x] 3.2 在 workflow compile 中实现“写入节点推导”：基于每个 run 的 effective outputs 列表与其 `to/write` 绑定生成等价 write nodes（`append_sheet`/`write_sheet`）,并以 `workflow.runs` 顺序 + `outputs` 顺序作为写入 SSOT（不依赖并发完成时序）。
- [x] 3.3 实现同一 `book_id` 的写入串行化：在 workflow IR 中对同一 book 的写入节点生成确定性的依赖链（等价于旧 `last_write_node_id_by_resource` 思路）,保证确定性与可复现性。
- [x] 3.4 实现 `.xlsx` 输出路径冲突预检：覆盖 `books.kind=xlsx_file.path` 与 `books.kind=xlsx_memory.export_xlsx.path`（当存在），并要求使用最终渲染/解析后的路径参与冲突判断（含 `{$init_var: ...}` 与 `$ctx` 渲染后的值）。

## 4. Workflow Resources：workbook/sheetbook 收敛为 `books`

- [x] 4.1 将 `src/scalim/workflow/resources_workbook.py` 与 `resources_sheetbook.py` 的对外能力收敛为 `books` 资源(kind=`xlsx_file|xlsx_memory`),并将资源注册表从按类型分裂(`workbooks/sheetbooks`)迁移到按 kind 分发。
- [x] 4.2 保持关键写入契约不回退：原子落盘/commit-all-or-discard、写锁语义、公式转义默认开启 + `allow_formulas` 显式 opt-out、xlsx_memory 预算护栏与超限 fail-fast。
- [x] 4.3 清理 workflow CSV shared resources 面：移除或 internalize `workflow.resources.csvs` 与相关 write intents（`csv_append`）,并确保对外文档/skills/examples 不再出现该 surface。

## 5. Builtin Loader：从 sheetbook 迁移到 xlsx_memory book

- [x] 5.1 新增并使用 `scalim.workflow.loaders:book_sheet_rows`（替代 `sheetbook_sheet_rows`）,参数 `ref` 结构改为 `{node, book, sheet}`；并保持“deps 闭包可见性”约束与可诊断错误信息。
- [x] 5.2 更新默认 builtin callable vocabulary：将 `^workflow/sheetbook_sheet_rows` 替换为 `^workflow/book_sheet_rows`；更新 public ids 列表与错误提示。

## 6. Python Public API：IO-only overrides（run / run_workflow）

- [x] 6.1 扩展 `src/scalim/dsl/by_yaml/runtime/contracts.py:RunOverrides` 支持 IO-only overrides：`overrides.resources.books` 与 `overrides.outputs_defaults.to.book`（deep-merge）,同时保留 `overrides.outputs` 的 replace 语义作为高级 escape hatch。
- [x] 6.2 在 demand compile 与 workflow compile 中落地 overrides 优先级：demand YAML < workflow YAML < Python overrides；并保证错误路径指向 `overrides.*` 的可定位路径（例如 `overrides.resources.books.report.kind`）。
- [x] 6.3 增加回归测试覆盖 overrides：至少覆盖“仅覆盖 path/预算不重复声明全部 keys”的 deep-merge 行为,以及 `overrides.outputs` 仍然 wins 的 replace 行为。

## 7. Repo 级迁移：测试/示例/skills 统一升级到新写法

- [x] 7.1 更新/重写 workflow 测试以移除 `writes` 与 pathless CSV：
  - `tests/test_yaml_dsl_workflow.py`（shared workbook/sheetbook/writes/pathless 相关用例整体迁移为 books + 推导写入节点）
  - `tests/test_yaml_output_pathless_csv.py`、`tests/test_output_composition_in_memory_csv.py`、`tests/test_yaml_parser_outputs_internal.py`（删除或改写为“schema/runtime 拒绝 pathless/workbook container”）
- [x] 7.2 更新 skill generator 测试与生成逻辑：`tests/test_agent_skill_generator.py` 断言更新为 `workflow.resources.books` 且不再包含 `workflow.runs[*].writes`；运行 `just gen-agent-skill` 并通过 `just validate-agent-skill`。
- [x] 7.3 迁移 docs/skills 中的 workflow 写入示例：
  - `docs/doc/yaml-dsl/workflow.md`（删除 `writes`/`workbooks/csvs/sheetbooks` 叙述,改为 `workflow.resources.books` + demand outputs 绑定）
  - `artifacts/skills/scalim-yaml-dsl/references/task-workflow-authoring.md`（同上,并更新 loader 示例为 `book_sheet_rows`）
  - `artifacts/skills/scalim-yaml-dsl/references/task-authoring.md`（移除 `outputs.*.container.path: {$init_var: ...}` 的输出路径示例,迁移到 `resources.books.*.path`）
- [x] 7.4 若仓库内存在 workflow demo baseline/生成脚本依赖旧写法,更新其 YAML 与生成入口（例如 `just gen-viz-workflow-demo-big-data-report` 相关输入）。

## 8. Docs / SSOT 治理（生成物与漂移门禁）

- [x] 8.1 更新 OpenSpec specs index 与相关引用(如有)并运行 `just openspec-check`（sanitize + validate）。
- [x] 8.2 更新 docs 站点内容并刷新生成物：运行 `just gen-docs` + `just docs-drift-check` + `just doc-governance-check`。
- [x] 8.3 运行 `just check-api-surface-governance` 确保 public entrypoints/`__all__` 治理未被破坏（特别是 by_yaml overrides/public loader ids 的变更）。

## 9. 验收/验证命令（建议顺序）

- [x] 9.1 `just gen-yaml-dsl-schema && just schema-drift-check`
- [x] 9.2 `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/demand.gen.json <demand.yaml>`
- [x] 9.3 `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>`
- [x] 9.4 `uv run scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- [x] 9.5 `just test`（或最小子集 + 覆盖新增/更新用例）
- [x] 9.6 `just py36-compat-check && just py36-typingext-check`（确保 `src/scalim/` 运行时边界不被破坏）
- [x] 9.7 `just qa`（最终门禁）
