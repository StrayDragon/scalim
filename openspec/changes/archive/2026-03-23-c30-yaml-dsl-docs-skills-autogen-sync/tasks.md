## 0. 边界与基线（先写死口径）

- [ ] 0.1 明确本变更的 SSOT/生成物/注入区块边界（CLI parser、schema `*.gen.json`、docs `*.gen.md`、skill `references/generated/**`、以及 docs/skill 中的 injected blocks）
- [ ] 0.2 盘点当前 docs/skill 中“可复制命令片段”的手写位置，确定本变更要禁止手写的目标文件清单（MVP 先收敛到 `workflow.md`/`agent-skill.md`/`SKILL.md`）
- [ ] 0.3 固化分步验收里程碑（M1~M5）：每一步都必须能用 `just gen-docs --check` / `just validate-agent-skill` / `just qa` 给出可回归的失败信号

## 1. CLI docs 摘录（SSOT: CLI parser）

- [ ] 1.1 扩展 `packages/scalim-misc/src/scalim_misc/cli_docs.py::build_yaml_dsl_command_docs()` 覆盖 `yaml-dsl upsert-lsp-comment`
- [ ] 1.2 新增共享 renderer（输出 Markdown，供 docs/skill 共用）：完整 CLI reference + 最小命令片段（统一 header：generated/do-not-edit）
- [ ] 1.3 单测：命令录制清单包含 `upsert-lsp-comment`；渲染结果稳定（同输入重复渲染一致）

## 2. docs-site 自动同步（SSOT: CLI 摘录 + schema `*.gen.json`；入口: `just gen-docs`）

- [ ] 2.1 `scripts/gen-docs.py` 新增生成页：`docs/doc/yaml-dsl/cli-reference.gen.md`（禁止手改；验收：`just docs-drift-check` / `just qa`）
- [ ] 2.2 扩展 `docs/doc/yaml-dsl/schema-reference.gen.md`：在现有 demand reference 基础上追加 workflow schema reference（SSOT: `src/scalim/dsl/by_yaml/schema/workflow.gen.json`；入口: `just gen-docs`）
- [ ] 2.3 在 `docs/doc/yaml-dsl/workflow.md` 与 `docs/doc/yaml-dsl/agent-skill.md` 增加 injected block markers，并将“可复制命令片段”迁移到注入区块（禁止手改区块内部）
- [ ] 2.4 验收：`just gen-docs`、`just docs-drift-check`、`just qa`
  - 验收点：生成的 CLI reference 必须包含 `yaml-dsl upsert-lsp-comment` 的 command details（usage/help_full），不允许缺失

## 3. skill 自动同步（SSOT: 同一 renderer；入口: `just gen-agent-skill`）

- [ ] 3.1 在 `artifacts/skills/scalim-yaml-dsl/SKILL.md` 增加 injected block markers（仅注入最小命令片段；marker 外仍保持手工 routing-first）
- [ ] 3.2 更新 `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`：对 `SKILL.md` 执行 injected blocks 注入；并确保 `references/generated/cli-lsp-reference.gen.md` 覆盖 `upsert-lsp-comment`
- [ ] 3.3 验收：`just gen-agent-skill`、`just validate-agent-skill`
  - 验收点：生成的 skill reference 必须包含 `yaml-dsl upsert-lsp-comment` 的 command details（usage/help_full），不允许缺失

## 4. 治理门禁（强约束：禁止手写片段）

- [ ] 4.1 新增检查脚本（或扩展现有 `scripts/check-doc-governance.py`）：目标文件缺 marker 或 marker 外出现手写命令片段则失败；错误信息必须给出修复入口（`just gen-docs` / `just gen-agent-skill`）
- [ ] 4.2 将检查接入 `quick-check-only-py`（因此进入 `just qa`）；并确保 CI 下也可稳定运行
- [ ] 4.3 单测：缺 marker / marker 外命中模式均 fail-fast；marker 内允许出现命令片段

## 5. OpenSpec 校验与规范同步

- [ ] 5.1 验收：`just openspec-check`
- [ ] 5.2 归档前将 delta specs 同步到 `openspec/specs/`（`yaml-dsl-docs-skills-autogen-sync`、`yaml-dsl-agent-guidance`）
