# Future — xlsx-file-numeric-type-loss

> 未完成候选池（非 active change）。来源归档：`c5-xlsx-file-numeric-type-loss`。  
> 已完成项已移出；升格须新建 `llmanspec/changes/cN-...` 并引用本文件。

**已承接（勿再当作 open work）**

- typed `xlsx_file` / ROWS SSOT、openpyxl helpers、streaming column sink、c30 释放 → 已归档
- 内存总线**语义** → **`archive/2026-07-13-c15-decide-xlsx-memory-book-role`**
- 统一 authoring `xlsx` + 旧 kind deprecated → **`archive/2026-07-13-c20-add-unified-xlsx-book-kind`**
- IR 身份改为 path 有无（不再以假 kind 字符串为 SSOT）→ **`archive/2026-07-13-c25-normalize-xlsx-book-ir-path-presence`**
- BREAKING 硬删 YAML `xlsx_file`/`xlsx_memory` 别名 → **`c999-remove-deprecated-xlsx-file-memory-kinds`（已实施；见 upgrade `2026-07-20-remove-deprecated-xlsx-file-memory-kinds`）**
- book cell/sheet 预算 / `BookBudgetPolicy` → **已移除**（upgrade `2026-07-28-remove-book-budget-policy`；残留 YAML/`RunOverrides` `budget` 仍 fail-fast，删字段；内存交宿主限制）
- 默认 deprecate/删除总线、无条件急切 CSV 双份、启发式数字恢复 → **已拒绝**
- ~~有 path 的 book 可选 cell/sheet budget~~ → **取消**（挂 `BookBudgetPolicy`；该 API 已移除，不再做 pathful 对称护栏）

---

## Deferred Items

### later — 按 consumer 显式派生 CSV

- **状态**: **显式派生机制已落地**——`MANAGED_ARTIFACT_KIND_CSV/ROWS` 闭集 + `_collect_managed_artifact_outputs`（`execution/run_ir.py`）对 ROWS 计划不急切复制 CSV；剩余缺口仅为「ROWS-only 输出 + CSV consumer」自动升格。
- **必要？** **有条件必要**。合约缺口仍在（ROWS-only + CSV consumer → `Missing workflow-managed in-memory CSV artifact`，`workflow/input_artifacts.py`）；匿名侧尚无双消费证据。
- **触发**: 真实「单 output → xlsx + csv」或报告 `Missing workflow-managed in-memory CSV artifact`。
- **落地**: `add-managed-artifact-consumer-driven-csv`
- **约束**: 禁止恢复无条件 `to_csv_artifact()`；派生须显式、与 ROWS 同释放（现状已满足）。

### later — 合并 workbook / sheetbook **实现**模块

- **必要？** **值得保留，但排在 c20/c25 之后**。产品名已由 `xlsx` 统一；双后端仍是漂移/spill 成本。
- **触发**: 同算法双改漏改；或 spill/seal/budget 必须两套都做。
- **落地**: `refactor-workflow-xlsx-backends-unify`
- **注意**: ≠ 删总线语义；≠ 替代 c20/c25/c999。

### later — shared-book 分段 spill / 分段 commit

- **必要？** **有 bench 才必要**。c30 后峰值仍可能卡在 plan∑segments。
- **触发**: 可复现 shared-book peak ROI（证据进 `.tmp/`）。
- **落地**: `shared-book-spill-commit`；禁止默认边写 openpyxl。
- **前置**: c20/c25 正规化后更易做；完整模块合并为软前置。

### done — `FieldValue` 纳入 openpyxl 时间类型

- **状态**: **已实现并归档**（commit `d5aa943c`；change `2026-07-18-c0-add-field-value-datetime`，2026-07-28 冻结于 `freezed_changes.7z.archived`）。`FieldValue` 现含 `datetime`/`date`/`time`/`timedelta`（`src/scalim/typedefs.py`）。
- **定案**: 含 `datetime`/`date`/`time`/`timedelta`；撤中间态 `str()`；**不去 tz**（与 openpyxl 同源报错）。
- **勿重复**: notplan 同名目录仅为指针 stub；勿再开平行 change。

### later — output bypass / 非托管写出

- **必要？** **仅强产品需求时**。动原子 commit/discard，成本高。
- **触发**: 明确要求立即落盘且下游按文件读。
- **落地**: 独立 explore → propose。

### later — sheet seal（Python policy）

- **必要？** **低优先**。与内存无关；无产品信号可不动。
- **触发**: 审计/不可变 sheet。
- **落地**: `shared-book-sheet-seal`；**禁止 YAML knobs**。

### cancelled — 有 path 的 book 可选 cell/sheet budget

- **状态**: **取消**。原计划挂 `BookBudgetPolicy`；该 API 已在 `2026-07-28-remove-book-budget-policy` 移除，不再做 pathful 对称护栏。
- **替代**: 内存风险交宿主 cgroup / OOM / 作业配额。

### done — `BookBudgetPolicy` 限流或移除

- **状态**: **已移除**（不做限流）。见 upgrade `2026-07-28-remove-book-budget-policy` / change `c0-remove-book-budget-policy`。
- **保留**: `BookWritePolicy`；workflow `cache_pool` budget（另一套能力）。

### later — 边写 openpyxl + runtime profile

- **必要？** **暂不必要**。破坏默认原子 discard。
- **触发**: profile 档位明确可牺牲 discard。
- **落地**: notplan profiles → change；**禁止 YAML**。

---

## Triggers to Reopen

1. `book_sheet_rows` 在「有 path / 无 path」书上可见性不一致 → hotfix。
2. 单 output 双消费缺 CSV → 升格 consumer-driven CSV。
3. 提议恢复无条件 `to_csv_artifact()` → **拒绝**，改显式派生。

## Traceability

| 字段 | 值 |
|---|---|
| Source | archive `c5-xlsx-file-numeric-type-loss` |
| Active authoring (archived) | `archive/2026-07-13-c20-add-unified-xlsx-book-kind` |
| IR path-presence (archived) | `archive/2026-07-13-c25-normalize-xlsx-book-ir-path-presence` |
| BREAKING remove aliases (implemented, frozen) | `archive/2026-07-20-c999-remove-deprecated-xlsx-file-memory-kinds`（commit `2db49202`；冻结于 `freezed_changes.7z.archived`） |
| Spec anchors | shared-output r24；managed-temp r1；intermediate-store r2/r7 |
