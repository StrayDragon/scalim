## 1. Docs 对齐 workflow schema（用户侧可用）

- [x] 1.1 更新 `docs/doc/yaml-dsl/workflow.md`：补齐 `depends_on/init_vars/options.ctx/resources/write_to`、并发契约、以及 workflow 的校验命令（repo 内显式 `--schema .../workflow.gen.json`）
- [x] 1.2 更新 `docs/doc/yaml-dsl/workflow.md`：补齐 LSP 指引（`yaml-dsl schema-serve` + `upsert-lsp-comment --type workflow` + `$schema: .../workflow.gen.json`）
- [x] 1.3 更新 `docs/doc/yaml-dsl/agent-skill.md`：补齐 workflow references 与 workflow 校验/LSP 命令入口（说明 `.gen.`/AUTOGEN 治理与生成入口）

## 2. Skill 手工部分扩展到 workflow（routing + 最小命令）

- [x] 2.1 更新 `artifacts/skills/scalim-yaml-dsl/SKILL.md`：新增 workflow authoring/validate/debug 的任务分流与最小命令（强调 workflow 仅 schema-only 校验；不得建议对 workflow 跑 `yaml-dsl validate`）
- [x] 2.2 新增手工 reference：`artifacts/skills/scalim-yaml-dsl/references/task-workflow-authoring.md`（包含最小可用模板 + 常见坑：deps 可见性、ctx 边界、resources/write_to 互斥、cycle/冲突等）
- [x] 2.3 新增手工 reference：`artifacts/skills/scalim-yaml-dsl/references/task-workflow-validate-debug.md`（schema error path 读法、常见互斥/缺失资源诊断、推荐命令组合）

## 3. Upgrades 收敛：新增一条 workflow 批次索引（SSOT → docs 生成）

- [x] 3.1 新增 SSOT：`artifacts/skills/scalim-yaml-dsl/references/upgrades/2026-03-18-yaml-workflow-dag-ctx-resources.md`（变更摘要 + Migration Checklist；覆盖 DAG/ctx/resources/sheetbook/write_to）
- [x] 3.2 运行 `just gen-docs` 生成对应 upgrades 页面（禁止手改 `docs/doc/yaml-dsl/upgrades/*.gen.md`）

## 4. 生成器扩展：generated references 覆盖 workflow（受控生成 + 漂移门禁）

- [x] 4.1 更新 `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`：纳入 `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 作为输入；扩展 `references/syntax-catalog.gen.md` 输出 workflow 语法索引
- [x] 4.2 更新 `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`：扩展 `references/generated/cli-lsp-reference.gen.md`，加入 workflow 校验与 `upsert-lsp-comment --type workflow` 指引
- [x] 4.3 更新 generator 的 coverage_index：纳入 workflow 相关 OpenSpec specs（例如 `yaml-dsl-workflow`、`workflow-cache-pool`、`workflow-sheetbook-resources` 等）以便回归追踪
- [x] 4.4 更新 `tests/test_agent_skill_generator.py`：断言 syntax catalog/CLI reference 中包含 workflow 关键字段与命令示例（`depends_on/init_vars/resources/write_to/ctx`、`--type workflow`）
- [x] 4.5 运行 `just gen-agent-skill` 并提交生成物；运行 `just validate-agent-skill` 作为验收（manifest 变化为预期）

## 5. OpenSpec 元信息修复：消除 “TBD” 覆盖观感问题（SSOT → docs 生成）

- [x] 5.1 更新 `openspec/specs/workflow-sheetbook-resources/spec.md`：补齐 Purpose/状态行（不改 REQUIREMENTS）
- [x] 5.2 运行 `just gen-docs` 刷新 `docs/doc/specs/openspec-index.gen.md`（禁止手改 `.gen.` 文件）

## 6. 统一验收（漂移与规范门禁）

- [x] 6.1 运行 `just openspec-check`：确保 OpenSpec artifacts 结构校验通过
- [x] 6.2 运行 `just qa`：确保测试/漂移门禁通过（至少包含 docs 与 agent-skill 的 drift checks）
