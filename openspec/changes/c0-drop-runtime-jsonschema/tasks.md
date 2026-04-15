## 1. Runtime：移除 JSONSchema 校验主线

- [ ] 1.1 移除 `src/scalim/` runtime 校验链路对 `jsonschema` 的可选导入与 `HAS_JSONSCHEMA` 分支（不再输出 schema-skip warning）
- [ ] 1.2 删除/收敛 `enable_jsonschema_validation` 等开关在 runtime 入口中的传递（loader / validation_service / compiler_frontend 等统一升级为单主线）
- [ ] 1.3 审计并补齐“原本依赖 JSONSchema 才能兜底”的结构/类型约束：运行时必需约束补到语义 validator 或 parser fail-fast；编辑器友好约束留给 schema-only

## 2. CLI：职责边界与依赖声明

- [ ] 2.1 更新 `scalim-cli yaml-dsl validate` 回归用例：不再期望任何 “已跳过 schema 校验 / jsonschema 不可用” warning
- [ ] 2.2 确认 `scalim-cli yaml-dsl schema validate` 仍使用 JSON Schema 并保持完整错误收集与稳定排序（必要时补充/调整回归用例）
- [ ] 2.3 更新 `packages/scalim-cli/README.md`：写清 `schema validate` 依赖 `jsonschema`、validate vs schema validate 的职责边界与选择建议（依赖由 CLI 发行物自身声明）

## 3. 规范/治理：落盘与验收

- [ ] 3.1 将本 change 的 delta specs 同步到 `openspec/specs/framework-logging/spec.md` 与 `openspec/specs/yaml-dsl-cli-validation/spec.md`（确保 REQUIREMENTS 与实现一致）
- [ ] 3.2 运行 `just openspec-check` 验证工件可共享（sanitize + OpenSpec validate）；必要时补充最小修正
- [ ] 3.3 运行 `just qa` 作为验收门禁（lint/tests + drift checks），确保无生成物漂移（如涉及 docs 注入/生成则走 `just gen-docs`）

