## Context

workflow YAML 的写入 surface 已从 `workflow.runs[*].write_to` 迁移为 `workflow.runs[*].writes`（list of intents）,并在 runtime/schema 校验层面以 `writes` 作为唯一真相.

但 `scalim-yaml-dsl` skill 的生成语法目录 `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 在 workflow “Key Paths” 中仍输出了 `workflow.runs[*].write_to`,导致:

- 作者体验：用户按文档写旧字段会直接失败
- LSP/可视化编辑：key path 搜索与诊断路径不一致,影响定位与对拍
- 维护成本：生成物缺乏可信的“与 schema 一致”的保障

本变更以 workflow schema 为 SSOT,修复生成器的硬编码漂移,并补齐回归测试与生成门禁.

## Goals / Non-Goals

**Goals:**
- `references/syntax-catalog.gen.md` 的 workflow “Key Paths” MUST 包含 `workflow.runs[*].writes`,且 MUST NOT 包含 `workflow.runs[*].write_to`
- `openspec/specs/agent-skill-export/spec.md` workflow 关键字段索引与 `writes` 对齐
- 用测试锁定生成结果,避免后续 drift

**Non-Goals:**
- 不改动 workflow runtime/IR/schema（不引入 `write_to` 兼容层）
- 不在本变更内全面重写所有历史升级文档（仅修复本次 drift 触发点）

## Decisions

- D1. 以 `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 为 workflow YAML 的唯一真相：生成器不得硬编码已移除字段名.
- D2. 生成器从 schema 提取 run 字段（包括 coverage index 与 key paths）时统一使用 `writes`.
- D3. 添加回归测试：断言生成的 syntax catalog 只出现 `writes`,并显式拒绝 `write_to`.

## Risks / Trade-offs

- [风险] repo 其他手工文档可能仍出现 `write_to` 旧表述 → [缓解] 本变更先修复生成器与核心 spec,并用测试把漂移锁住；其余历史文档可另起 change 做系统性清理.
- [风险] 生成物刷新可能引入大 diff → [缓解] 只通过既有 `just gen-agent-skill` 刷新,不手改 `.gen.*` 与 injected blocks.
