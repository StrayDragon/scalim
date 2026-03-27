## 0. SSOT 整理与清理

- [ ] 0.1 将 `_NEXT/` 与 `.tmp/api-surface-audit-report.md` 迁移到 `openspec/changes/c0-api-surface-governance/references/`
- [ ] 0.2 删除 `_NEXT/` 与 `.tmp/api-surface-audit-report.md`，确保本 change 为唯一来源
- [ ] 0.3 运行 `just openspec-check` 校验 OpenSpec 工件结构与 sanitize 规则

## 1. 规范与门禁（public surface governance）

- [ ] 1.1 为 `public-api-surface-governance` 增量补充：禁止 `__all__` 导出 `_...` 内部符号
- [ ] 1.2 为 `public-api-surface-governance` 增量补充：内部实现模块（`_internal/` 或 `_` 前缀模块）必须显式 `__all__ = []`
- [ ] 1.3 增加/更新回归门禁（pytest AST 扫描或脚本）以 enforce 1.1/1.2，并纳入 `just qa`

## 2. Phase 1：`__all__` 封堵（分批 ≤10 文件，每批后 `just qa`）

- [ ] 2.1 修复审计报告中 `__all__` 的 `_...` 泄漏模块（先 workflow/resources_* 与 by_yaml/runtime/conversion）
- [ ] 2.2 为 `_internal/` 子目录下的实现模块补齐 `__all__ = []`（按 area 分批推进）
- [ ] 2.3 为剩余“缺失 `__all__` 且非稳定入口”的模块补齐 `__all__ = []`（优先 CLI/utils/vendor 等散模块）

## 3. Phase 2：入口目录与导入收敛策略

- [ ] 3.1 对照 `src/scalim/__init__.py` 与 `openspec/specs/public-api-surface-governance/spec.md`，确认稳定入口目录是否需要扩展（例如 `sinks`/`events`/`hooks`/`types`）
- [ ] 3.2 若扩展稳定入口：补齐对应 `__all__` 白名单与 examples gate 覆盖（`notebooks/marimo/` public API suite）
- [ ] 3.3 若不扩展：明确 docs/skills/examples 的推荐导入路径与禁止路径，并在 gate 中做字符串/AST 扫描守护

## 4. Phase 3：内部实现封装（BREAKING，按包独立批次推进）

- [ ] 4.1 设计并试点一个包的内部封装（例如 `utils` 或 `sinks`）：`git mv` + 全仓引用迁移 + `just qa`
- [ ] 4.2 推进其余包的封装/重命名（events/hooks/spec/ir leaves 等），每包独立批次并在每批后 `just qa`
- [ ] 4.3 移除遗留 shim/兼容层（若存在），确保旧路径不再可用

## 5. Phase 4：外部引用迁移（tests/ → packages/ → notebooks/）

- [ ] 5.1 批次迁移 `tests/` 的导入路径到推荐路径（只改 import 行，不改断言/fixture/逻辑）并 `just qa`
- [ ] 5.2 批次迁移 `packages/` 的导入路径并 `just qa`
- [ ] 5.3 批次迁移 `notebooks/` 的导入路径并 `just qa`

## 6. 验收与回归

- [ ] 6.1 `just qa` 全绿（lint/tests/drift/openspec-check）
- [ ] 6.2 若涉及 docs-site：运行 `just gen-docs` 并确保无生成物漂移

