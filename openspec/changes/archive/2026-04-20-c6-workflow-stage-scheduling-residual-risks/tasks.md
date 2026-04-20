## 1. Sync spec (SSOT)

- [x] 1.1 将本 change 的 delta spec 同步到 `openspec/specs/workflow-stage-scheduling-residual-risks/spec.md`（SSOT：手写文件）
- [x] 1.2 复核与 `openspec/specs/workflow-stage-scheduling/spec.md` 的一致性（默认值、术语与 stage 折叠边界）

## 2. Docs generation & gates

- [x] 2.1 运行 `just gen-docs` 刷新 docs-site 生成页与 injected blocks（禁止手工编辑任何 `*.gen.*` 文件或 `BEGIN/END AUTOGEN:*` 区块）
- [x] 2.2 运行 `just openspec-check`（sanitize + validate）作为 OpenSpec 验收门禁
- [x] 2.3 运行 `just qa`，确保无文档漂移与质量门禁回归
