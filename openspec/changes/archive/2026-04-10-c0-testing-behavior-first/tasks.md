## 1. Branch Coverage 门禁迁移（配置为 SSOT）

- [x] 1.1 跑一次基线：执行 `just test`，记录当前 coverage 输出（含 branch 口径的总百分比），确定一个不会阻塞历史但能防回退的 Stage-0 初始阈值
- [x] 1.2 更新 `pyproject.toml`（SSOT）：启用 `--cov-branch`（或等价配置），将 `--cov-fail-under` 从 statement-only 的 `100` 调整为基于 branch coverage 的 Stage-0 阈值（保持 `just test`/`just qa` 命令不变）
- [x] 1.3 （可选）补齐 `[tool.coverage.report]`（或等价配置）：让 QA 输出更可读且稳定（例如 precision/show_missing/skip_covered 等），并确认不引入需要提交的生成物

## 2. 行为契约与 Golden 治理落地（为后续变更铺路）

- [x] 2.1 在 `tests/fixtures/` 下补充最小约定文档（SSOT=仓内文档文件）：说明 fixtures/snapshots 的目录结构、`schema_version` 约定、以及 `UPDATE_GOLDEN=1` 的显式更新流程
- [x] 2.2 梳理并固化“默认都进”的策略：contract tests 不引入额外 `contract` marker 作为分组门禁，本地与 CI 使用相同的 `pytest` 入口（验收：`just test` 覆盖 contract tests）

## 3. 验收与回归口径

- [x] 3.1 验收：运行 `just qa`，确认 branch coverage 被采集并出现在门禁输出中，且不再被 statement coverage 的 `100%` 数字目标误导
- [x] 3.2 运行 `just openspec-check`，确保变更工件结构与脱敏校验通过
