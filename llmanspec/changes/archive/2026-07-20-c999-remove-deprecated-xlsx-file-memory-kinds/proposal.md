---
depends_on: []
blocks: []
---

# remove-deprecated-xlsx-file-memory-kinds

> 前置（已归档）：`normalize-xlsx-book-ir-path-presence` / `add-unified-xlsx-book-kind`

## Why

`add-unified-xlsx-book-kind` 已把推荐 authoring 收敛为 `books.<id>.xlsx`（path 可选），并以 warning 保留 `xlsx_file` / `xlsx_memory` 别名；`normalize-xlsx-book-ir-path-presence` 已把运行时身份收敛为 **pathful / pathless**。

过渡期双路径仍在扩大技术债：

1. YAML 仍接受 deprecated 别名（+ `DeprecationWarning` / validate warning）
2. Python/IR 仍有 `kind=xlsx_file|xlsx_memory` wire shim（`BookConfig.kind`、`legacy_kind_shim`、`get_book_kind`）
3. 其它静默/弱兼容：`observability` YAML strip+warning、`typedefs.RowId*` 别名

需要一次显式 BREAKING 革新：硬删旧 YAML/kind 兼容层，同时**保留**好用的 Python shortcut 工厂接口名（内部切到最新 identity）。

## What Changes

1. **YAML BREAKING**：schema / parse / validator **拒绝** `resources.books.*.xlsx_file` / `xlsx_memory`（含挂在 memory 上的 `export_xlsx` 别名路径）；错误信息指向 `xlsx` + path 语义与 upgrade 笔记。
2. **删除** deprecated warning 路径与兼容测试；迁移文案保留在 dated upgrade 笔记（Before 仅作历史）。
3. **Python/IR kind shim 终态**：运行时身份仅 pathful/pathless；MUST NOT 再把 `xlsx_file`/`xlsx_memory` 字符串当作 IR/runtime 业务身份 SSOT；移除（或降级为非契约内部细节后删除）`legacy_kind_shim` / `get_book_kind` 对外语义依赖。
4. **保留 shortcut API（兼容面）**：`RunOverrides.xlsx_file_single_sheet`（及同模块既有工厂函数）**名称与调用签名 MUST 保持稳定**；实现 MUST 改为构造与 `xlsx.path` / pathful 等价的 identity（调用方无需改调用点）。
5. **observability**：已知 legacy YAML `observability.*` 从「warning + strip 忽略」升级为 **fail-fast**（迁移提示指向 Python/CLI runtime entrypoints）。
6. **typedef 别名**：移除公开 `RowId` / `RowIdSeq` / `RowIdList`；调用方改用 `BusinessKey` / `Sequence[BusinessKey]` / `List[BusinessKey]`；`LoaderResult` 等内部类型随之对齐。
7. skills / 语法目录 / 示例：只出现 `xlsx`；历史 Before 块可留在 dated upgrade 笔记。
8. **不做**：删除内存总线语义；合并 workbook/sheetbook 实现模块；把 write/budget 写回 YAML；重命名 `xlsx_file_single_sheet` 工厂。

## Capabilities

### Modified Capabilities

- `yaml-dsl-books-resources` — BREAKING 移除 deprecated book 分支；强化 pathful/pathless SSOT；更新相关 wording
- `yaml-dsl-observability-boundary` — legacy `observability.*` 升级为 fail-fast
- `yaml-dsl-output-overrides` — 明确工厂名稳定 + 内部 pathful 实现
- `workflow-managed-temp-outputs` — consumer 表述从旧 kind 字符串改为 pathful/pathless

### New Capabilities

- `runtime-typedef-aliases` — 移除 `RowId*` 公开兼容别名

## Impact

- **破坏性**：是（旧 YAML 别名直接 fail-fast；kind wire 依赖方需改；`RowId*` import 需改；YAML `observability.*` 不再被忽略）
- **兼容保留**：`RunOverrides.xlsx_file_single_sheet` 等工厂 **调用面不变**
- **迁移**：
  - `xlsx_file:{path}` → `xlsx:{path}`
  - `xlsx_memory:{}` → `xlsx:{}`
  - `xlsx_memory.export_xlsx.path` → `xlsx.path`
  - YAML `observability.*` → Python/CLI observers/hooks
  - `RowId` → `BusinessKey`
- **隐私**：示例继续只用虚构 id/path
- **Docs/SSOT**：upgrade 笔记、skills、`just gen-docs`；禁止手改 `*.gen.*`

## Ethics

- `ethics.risk_level`: medium（BREAKING 面清晰，但下游 YAML/二开可能仍有旧 kind）
- `ethics.prohibited_actions`: 不得静默改工厂函数名；不得把 write/budget 回流 YAML；不得在证据中入库真实外部路径
- `ethics.required_evidence`: 仓库内推荐示例/notebooks 无旧 YAML 分支；工厂回归测；fail-fast 文案含迁移提示
- `ethics.refusal_contract`: 若外部下游旧 kind 用量未清且用户要求“无迁移窗口硬删”，须先给出影响面再实施
- `ethics.escalation_policy`: 若发现公开 Tier-1 还依赖 `get_book_kind`/`RowId` 大面积外部引用，实施前向用户确认窗口
