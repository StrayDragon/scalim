# Design — remove-book-budget-policy

## Decision

完整删除 pathless book 的进程内 `BookBudgetPolicy` 护栏（同 cardinality 护栏移除哲学）。**保留** `BookWritePolicy` 与 `cache_pool` budget。

## Migration copy

残留 YAML / RunOverrides `budget` → fail-fast，文案统一为「已移除；请删除该字段，内存风险交宿主资源限制」，**禁止**再指向 `BookBudgetPolicy`。

## Surface map（实施时按此清）

1. Public：`BookBudgetPolicy`、`BookResourcePolicy.budget`、`ResourcesPolicy.budget_policy_for`、`__init__` 导出
2. Internal：`BookBudgetConfig` / `BookConfig.budget` / `BOOK_BUDGET_KEYS`（YAML 残留可用字符串 key 检测）
3. Materialize / compile：`materialize_resources_policy_onto_books`、`workflow_compile_resources` pathless options
4. Runtime：`SheetBookDef.budget_max_*`、`resources_sheetbook` 校验；`resource_defs` 双入口收敛
5. Override：`_apply_book_patch` 透传删除 + 拒斥文案更新
6. Specs（live）：r27 / r742 等改写为「不再提供」
7. Docs/skills/futures/demo/tests

## Test seams（pytest，无 `.feature`）

| Seam | 现有入口 |
|---|---|
| Python policy 构造 | `tests/yaml_dsl/test_book_resource_policy.py` / loader books coverage |
| YAML 残留 budget fail-fast | `tests/yaml_dsl/test_yaml_loader_books_io_coverage.py`、`test_c20_*` |
| pathless 写超限不再护栏 | `tests/yaml_dsl/test_yaml_dsl_workflow.py`（budget guard 用例改为「可写完」或删除） |
| RunOverrides budget patch | `resource_override` 相关 coverage |

## Out of scope

- pathful workbook 加 budget（futures 低优先项一并关闭/注明拒绝）
- cache_pool `over_budget_policy`
