---
depends_on: []
branch: sdd/c0-remove-book-budget-policy
base_sha: eeff547c347e361a04abb0892abf7da6ebc4ffdf
checkpointed: true
checkpoint_sha: eeff547c347e361a04abb0892abf7da6ebc4ffdf
---

## Why

`BookBudgetPolicy`（`max_sheets` / `max_total_cells`）是 pathless book（内存总线 / sheetbook）上的**进程内资源护栏**：默认 unlimited，显式配置后超限 **fail-fast**，无降级/背压。

与已归档的 `remove-derived-outputs-cardinality-guardrails` 同构：

1. 缺省无界 → 护栏对多数用户不生效；启用后只能失败，无法恢复。
2. 真实高内存风险更适合宿主层（cgroup / OOM killer / 作业配额）兜底。
3. 能力跨 Python policy、DemandConfig 物化槽、workflow compile options、`resource_defs` 接线、`resources_sheetbook` 运行期校验、YAML/RunOverrides 迁移 fail-fast、docs/skills/specs 多层铺开；**仓库内几乎仅 demo/测试使用，已知下游引用为 0**。
4. futures 已标注「用量≈0；限流或移除」（`llmanspec/futures/xlsx-file-numeric-type-loss/future.md`）；调研确认强制执行**仅**在 sheetbook，workbook 无平行实现，删除不会留下半截双后端护栏。

权衡：失去 pathless book 的进程内 sheet/cell 上限；换取更短策略面与与 cardinality 一致的「框架不做内存护栏」叙事。**保留** `BookWritePolicy`（写入语义，非护栏）。

## What Changes

**移除**

- 公开 API：`BookBudgetPolicy`；`BookResourcePolicy.budget` / `ResourcesPolicy.budget_policy_for`
- 内部槽：`BookBudgetConfig`、`BookConfig.budget`、`BOOK_BUDGET_KEYS`（若 YAML 残留检测仍需要，改为 validator 纯字符串 key 匹配，不保留 dataclass）
- 物化：`materialize_resources_policy_onto_books` 中 budget 分支
- workflow 编译：`workflow_compile_resources` pathless `book_options["budget"]`
- 定义/运行期：`SheetBookDef.budget_max_*`、`resources_sheetbook._check_sheetbook_budget` 与写 sheet 前 `max_sheets` 检查；`resource_defs` 中 book(pathless)/legacy sheetbook 两处 budget 赋值
- 测试/demo：`ch090` 等去掉 budget 示例；相关 workflow budget guard 测试删除或改为「不再护栏」
- Specs：改写 `workflow-shared-output-containers` r27、`workflow-sheetbook-resources` r742、`yaml-dsl-runtime-policy-boundary` / write-policy 中「Python BookBudgetPolicy 为 SSOT」表述 → 「不再提供 book cell/sheet 预算」
- 文档/skills/upgrade：capability-matrix、workflow.md、review-checklist、task-*、`2026-07-12-book-write-policy-python-ssot` 等去掉 budget 配置面；futures 该项勾为 done/removed
- 公开导出：`scalim.dsl.yaml_dsl.__init__` 去掉 `BookBudgetPolicy`

**迁移 / fail-fast（无兼容层）**

| 残留入口 | 行为 |
|---|---|
| YAML `resources.books.*.budget` / `xlsx.budget` / 旧 `xlsx_memory.budget` | 继续 fail-fast；提示改为「已移除；请删字段，内存风险交宿主」——**不要**再指向 `BookBudgetPolicy` |
| RunOverrides / `_apply_book_patch` 中 `"budget" in patch` | 继续 fail-fast；同上新文案 |
| Python `BookBudgetPolicy(...)` / `BookResourcePolicy(budget=...)` | 类型/参数不存在 → `TypeError` / `ImportError` |

**明确不改**

- `BookWritePolicy` / write_defaults Python SSOT
- workflow `cache_pool` budget / `over_budget_policy`（另一套能力）
- pathful workbook 写出路径（本就无 book budget）

## Surface notes（RunOverrides / 双后端）

- **强制执行只在 sheetbook**：`resources_workbook.py` 无 budget；删护栏不会在 workbook 留下半截。
- **接线重复**：`resource_defs.py` 的 `book+pathless` 与 legacy `sheetbook` 两段都灌 `SheetBookDef.budget_max_*`——删除时一并收敛。
- **RunOverrides**：typed `BookResourceOverride` 已无 `budget` 字段；`_apply_book_patch` 对 patch 内 `budget` fail-fast，并透传 `base.budget`。删除后：拒斥文案改为「已移除」，去掉透传与 `_validate_book_identity_contracts` 的 pathful+budget 检查。
- **勿误伤** `cache_pool` budget / `over_budget_policy`。

## Capabilities

- `workflow-shared-output-containers`
- `workflow-sheetbook-resources`
- `yaml-dsl-runtime-policy-boundary`
- `yaml-dsl-write-policy-and-output-extras`（文档/分工表述）

## Impact

- **BREAKING**：删除 `BookBudgetPolicy` 与一切启用后的 fail-fast 护栏行为。
- 缺省路径（未配 budget）行为不变（本就是 unlimited）。
- 迁移成本：删配置 + 改 fail-fast 文案；无算法替代。
- 指纹：不涉及 derived outputs 指纹；pathless book 写入失败模式变化仅当曾显式配预算。