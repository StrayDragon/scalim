## 1. Execution Tier1 Facade Re-export

- [ ] 1.1 调整 `src/scalim/execution/__init__.py`：更新 Tier1 marker 描述为 “execution facade（run_ir + contracts）”，并从包根 re-export `run_ir` 与 contracts（`ExecutionRequest/ExecutionResult/...`）；同时将 `ScalimEngine` 从 `__all__` 移除（验收：`from scalim.execution import ExecutionRequest, run_ir` 可用；`from scalim.execution import ScalimEngine` 不再作为 Tier1 用法）。
- [ ] 1.2 梳理并固定 execution 侧 public exports（验收：`scalim.execution` 的 `__all__` 仅包含本 change 约定的符号；`scalim.execution.run_ir.__all__` 与 contracts 不泄漏 internal 实现模块路径）。

## 2. Fail-fast Validation for `ExecutionRequest`

- [ ] 2.1 为 `ExecutionRequest` 增补 fail-fast 校验（按 design：结构性约束放 `__post_init__`；跨字段组合约束集中在 `run_ir` 入口），并确保错误信息包含字段路径（验收：非法组合在执行前报错；错误可定位到具体字段/组合）。
- [ ] 2.2 为新的 fail-fast 行为补充/更新测试（验收：新增用例覆盖至少 1 个跨字段组合非法场景；错误信息断言稳定）。

## 3. Migrate Imports in User Materials & Examples

- [ ] 3.1 全仓迁移用户材料与示例代码：将 `scalim.execution.run_ir` 模块路径导入改为 curated facade `scalim.execution`（验收：`docs/doc/**`、`notebooks/marimo/**`、`agentdev/skills/**` 中不再出现 `from scalim.execution.run_ir import ...`）。
- [ ] 3.2 迁移 tests/notebooks/packages 中的调用点（验收：`tests/public_api` 运行的 public API suite 全绿；示例套件导入路径仅使用 curated entrypoints）。

## 4. Public API Catalog / Generated Docs

- [ ] 4.1 刷新 public API 文档与审计生成物（验收：不手改 `docs/doc/getting-started/public-api.gen.md`；运行 `just gen-docs` 后无 drift，且 Tier1 表格反映新的 execution facade 导出面）。
  - SSOT：`src/scalim/execution/__init__.py` 与 `src/scalim/execution/run_ir.py` 的字面量 `__all__` + Tier1 markers
  - 生成入口：`just gen-docs`

## 5. QA / Drift Gates

- [ ] 5.1 OpenSpec 校验（验收：`just openspec-check` 通过；包含 sanitize + validate）。
- [ ] 5.2 Repo 质量门禁（验收：`just qa` 通过，包含 lint/tests + drift checks）。

