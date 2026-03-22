## Why

workflow YAML 的写入 surface 已以 `workflow.runs[*].writes`（list of intents）作为唯一真相,且 runtime 已明确移除 `write_to`.

但在 `scalim-yaml-dsl` skill 与相关 OpenSpec 文档中,仍残留若干 `write_to` 的旧表述（包括生成物中的 Purpose 文案与手工维护的升级/指引文档）,容易误导:

- 作者体验: 新用户按旧文案写 `write_to` 会在校验/运行阶段直接失败
- 工具链体验: 编辑器/LSP/可视化的搜索路径与文案不一致,降低定位效率
- 维护成本: “写入 intent” 语义难以作为稳定心智模型沉淀

## What Changes

本变更直接修复“文档层 write_to 残留”带来的作者误导,以 `writes` 为唯一真相进行统一.

- OpenSpec 文档:
  - 将 `workflow-sheetbook-resources` spec 中关于 `write_to.sheetbook_*` 的旧表述更新为 `writes[*].sheetbook_*`（或等价的 canonical path）
- skill 文档:
  - `artifacts/skills/scalim-yaml-dsl/SKILL.md`、workflow authoring/upgrades 文档中对 `write_to` 的表述更新为 `writes`
  - 若需要保留历史字段名,必须放在“迁移/历史”段落,并明确已移除与替代写法
- 生成物刷新（禁止手改生成物）:
  - 通过 `just gen-agent-skill` / `just gen-docs` 刷新 `.gen.md` 与注入区块

## Capabilities

### New Capabilities
- `skill-docs-write-to-cleanup`: 清理 `scalim-yaml-dsl` skill 与相关 OpenSpec 文档中把 `write_to` 作为当前 authoring surface 的残留表述,并将其收敛为明确的迁移/历史说明.

### Modified Capabilities
- `workflow-sheetbook-resources`: 更新写入 intent 的 canonical path 文案（`writes` 取代 `write_to`）,避免生成语法目录中的 purpose 漂移

## Impact

- 受影响 SSOT（预估,以最终 tasks 为准）:
  - `openspec/specs/workflow-sheetbook-resources/spec.md`
  - `artifacts/skills/scalim-yaml-dsl/SKILL.md`
  - `artifacts/skills/scalim-yaml-dsl/references/upgrades/*.md`
- 受影响生成物（禁止手改;需生成刷新）:
  - `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md`
  - `artifacts/skills/scalim-yaml-dsl/references/generated/yaml-dsl-upgrades.gen.md`
  - `docs/doc/specs/openspec-index.gen.md` 等 docs-site 生成物
