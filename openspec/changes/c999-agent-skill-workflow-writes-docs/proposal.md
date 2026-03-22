## Why

当前 `scalim-yaml-dsl` skill 的生成语法目录 `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 在 “Key Paths” 中仍出现了 `workflow.runs[*].write_to`，但实际 workflow YAML 的 schema 与 runtime 已以 `workflow.runs[*].writes` 作为唯一写入 surface。

这种“文档/索引字段名与真实语法不一致”会导致:

- 作者体验: 新用户按文档写 `write_to` 会在运行/校验阶段直接失败
- LSP/可视化编辑: key path 搜索与诊断路径不一致，影响定位与对拍
- 维护成本: 后续变更难以在 skill 参考中形成可信的 SSOT

## What Changes

本变更是一个 **proposal 保留**，不作为当前 workflow validate / render 的 MVP 交付物；用于记录后续需要补齐的“文档/索引一致性修复”工作。

计划修复点:

- OpenSpec 文档:
  - `openspec/specs/agent-skill-export/spec.md` 中 workflow 关键字段索引由 `write_to` 更新为 `writes`
- skill 生成器:
  - `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py::render_syntax_catalog(...)` 的 workflow “Key Paths” 输出改为 `workflow.runs[*].writes`（移除 `write_to`）
- 生成物刷新:
  - 通过 `just gen-agent-skill` 重新生成 `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md`
  - 不手改任何 `.gen.*` 与 injected blocks

## Capabilities

### Modified Capabilities
- `agent-skill-export`: workflow 语法索引字段名与 schema/runtime 对齐（`writes`）

## Impact

- 受影响 SSOT:
  - `openspec/specs/agent-skill-export/spec.md`
  - `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`
- 受影响生成物(禁止手改;需通过 `just gen-agent-skill` 刷新):
  - `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md`

