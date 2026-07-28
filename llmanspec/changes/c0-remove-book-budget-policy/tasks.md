## 1. Specs + 公开 API 拆除

- [x] 1.1 在 live specs 改写/删除 BookBudget 合约：`workflow-shared-output-containers` r27、`workflow-sheetbook-resources` r742、`yaml-dsl-runtime-policy-boundary` / `yaml-dsl-write-policy-and-output-extras` 中「Python BookBudgetPolicy SSOT」表述 → 「不再提供 book cell/sheet 预算」；配套 scenarios 同步
- [x] 1.2 删除 `BookBudgetPolicy` 与 `BookResourcePolicy.budget` / `ResourcesPolicy.budget_policy_for`；更新 `scalim.dsl.yaml_dsl` 导出与 public-api 生成入口（若有）
- [x] 1.3 删除/掏空 `BookBudgetConfig`、`BookConfig.budget`、`BOOK_BUDGET_KEYS`；物化路径不再写 budget

## 2. 编译 / 运行期 / override

- [x] 2.1 `workflow_compile_resources`：pathless 不再注入 `book_options["budget"]`
- [x] 2.2 `resource_defs` + `resources_sheetbook`：去掉 `budget_max_*`、`_check_sheetbook_budget` 与写 sheet 前 max_sheets 检查；收敛 book(pathless)/legacy sheetbook 双入口
- [x] 2.3 `resource_override`：去掉 `base.budget` 透传；`"budget" in patch` / YAML 残留 fail-fast 文案改为「已移除」（勿再提 BookBudgetPolicy）
- [x] 2.4 单测：policy 构造 TypeError、YAML/override 残留文案、原 budget guard 用例改为无护栏行为

## 3. 文档 / demo / 门禁

- [x] 3.1 新增 upgrade `agentdev/skills/scalim-yaml-dsl/references/upgrades/YYYY-MM-DD-remove-book-budget-policy.md`；更新 upgrades index / capability-matrix / workflow.md / review-checklist / task-* / `2026-07-12-book-write-policy-python-ssot`；futures 勾掉 book-budget 项
- [x] 3.2 更新 `ch090` 等 demo，去掉 `BookBudgetPolicy` 示例
- [x] 3.3 `just gen-docs`（若触及生成物）+ 相关 pytest + `llman sdd validate c0-remove-book-budget-policy --strict --no-interactive`
