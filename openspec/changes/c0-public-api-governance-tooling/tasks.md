## 1. Public API Export Catalog (Review Artifact)

- [ ] 1.1 新增 `scripts/gen-public-api-exports-catalog.py`：基于 Tier1 markers + 各模块字面量 `__all__`（AST-only，不 import）生成 `.tmp/public_api_exports_catalog.md` 审计视图（验收：产物按确定性顺序输出；入口模块缺少 marker 或缺少 `__all__` 时 fail-fast 且输出可定位信息）。
- [ ] 1.2 增加 `just gen-public-api-exports-catalog` 入口（验收：`just gen-public-api-exports-catalog` 可重复运行且二次运行无 diff；产物全部落在 `.tmp/` 且不提交）。

## 2. Curated Entrypoints Consistency Check (Gate)

- [ ] 2.1 新增 `scripts/check-public-api-curated-entrypoints.py`（或等价脚本）：校验 Tier1 markers 语法合法、无重复 module、module 必须存在且必须声明字面量 `__all__`（验收：错误输出包含文件路径 + 行号 + module 名 + 失败原因；无变更时输出稳定）。
- [ ] 2.2 增加 `just check-public-api-curated-entrypoints` 入口并接入 `just qa`/`just check-only-py`（验收：作为 fail-fast gate 在 marker/__all__ 漂移时能给出可修复提示）。

## 3. Existing Tooling Alignment

- [ ] 3.1 核对并补齐 `scripts/gen-public-api-jump-imports.py` 与 `just gen-public-api-jump-imports` 的约束：AST-only、确定性输出、入口模块必须有字面量 `__all__`（验收：生成 `.tmp/public_api_jump_imports.py`；重复运行无 diff）。
- [ ] 3.2 若 docs/README/开发指引需要提及新的生成/检查入口，更新 SSOT 文档并通过生成器刷新（验收：不手改任何 `*.gen.*` 与 injected blocks；运行 `just gen-docs` 后无 drift）。
  - SSOT：`docs/doc/**` 非 `*.gen.*` 源文件与 injected-block 外的内容
  - 生成入口：`just gen-docs`

## 4. QA / Drift Gates

- [ ] 4.1 OpenSpec 校验（验收：`just openspec-check` 通过；包含 sanitize + validate）。
- [ ] 4.2 Repo 质量门禁（验收：`just qa` 通过，包含 lint/tests + drift checks）。

