# Future — xlsx-file-numeric-type-loss

> 潜在 purpose 池（非 active change）。  
> 来源 change: `c5-xlsx-file-numeric-type-loss`  
> 路径约定: `llmanspec/futures/<kebab-id>/future.md`（仅本文件；无 proposal/tasks/specs）

审查条目时归类为 `now` / `later` / `drop`。升格为可执行工作须新建 `llmanspec/changes/cN-...` 并引用本文件条目。

---

## Deferred Items

### later — 按 consumer 显式派生 CSV（ROWS → CSV，禁止急切双份）

- **来源**: change `design.md` Collect 契约 — 本 change 只做「ROWS 不调用 `to_csv_artifact()`」；`in_memory_rows_to_in_memory_csv` 保留为显式工具，**不**实现「有 CSV consumer 时自动派生」。
- **缺口**: 若同一 demand output 同时被 `xlsx_*` write 与 `csv_file` / CSV write 消费，停急切副本后 CSV 侧会缺 `in_memory_csv_outputs`。
- **触发信号**:
  - 真实 workflow 出现「单 output → xlsx book + csv/file」双消费；或
  - 集成测/用户报告 `Missing workflow-managed in-memory CSV artifact`。
- **落地路径**（建议 change id）: `add-managed-artifact-consumer-driven-csv`
- **受影响 capability**: `workflow-managed-temp-outputs`, `workflow-intermediate-store` (r2/r7), `workflow-shared-output-containers`
- **设计约束（预案，非本 future 实现）**:
  1. Typed `InMemoryRows` 仍为 SSOT；CSV 仅为派生视图。
  2. 仅当编译期/运行期能证明存在 CSV-equivalent consumer 时才调用 `in_memory_rows_to_in_memory_csv`（或等价）。
  3. **禁止**恢复无条件 `ManagedArtifactPlan.to_csv_artifact()` 急切双份。
  4. 生命周期：派生 CSV 与 ROWS 一同参与最终 consumer 释放；失败 discard 两者。
  5. 诊断：缺 CSV consumer 却走 `resolve_workflow_input_csv` 时 fail-fast，提示改用 tabular 或声明 CSV consumer。
- **第一条动作**: `llman-sdd-propose` / `llman-sdd-ff` 建上述 change，把本条链进 proposal Why。

### later — 合并 workbook / sheetbook 实现模块

- **触发信号**: segment / 对齐 / openpyxl 写出持续双份漂移；或 `extract-openpyxl-shared-helpers` 落地后仍难共享。
- **落地路径**: `refactor-workflow-xlsx-backends-unify`
- **受影响 capability**: `workflow-shared-output-containers`, `workflow-runtime-module-organization`
- **备注**: `c5-xlsx-file-numeric-type-loss` 已对齐 **数据模型**（物化 typed rows）；文件级合并另案，避免与类型修复绑大 PR。
- **第一条动作**: 待 helpers change 归档后评估 diff 面，再 propose。

### later — output bypass / 非托管 book 写出

- **触发信号**: 产品明确要求「某 output 不走 workflow 资源管理器、立即落盘且可被下游按文件读取」。
- **落地路径**: 独立 change；必须重做原子 commit / discard 契约。
- **备注**: 源 change 明确否决从 bugfix 夹带 bypass。
- **第一条动作**: 先 `llman-sdd-explore` 澄清原子性与可见性，再 propose。

### later — `FieldValue` 纳入 `datetime`/`date`（Excel 原生日期）

- **来源**: pay-order 回归：loader 的 `datetime` 撞上 ROWS sink；草案在 `llmanspec/notplan/c0-add-field-value-datetime/`。
- **当前临时策略**: `InMemoryRowsSink` 对非 `FieldValue` `str()`（对齐旧 CSV）；Excel 单元格为文本日期。
- **阻塞**: openpyxl 拒绝 aware `datetime`；去 `tzinfo` 可能扭曲绝对时刻语义，需产品决策后再转正。
- **触发信号**: 需要 Excel 原生日期单元格 / 时区策略已收敛。
- **落地路径**: 将 notplan `c0-add-field-value-datetime` 转回 active change 后 apply。
- **第一条动作**: `llman-sdd-explore` 收敛 aware 策略（拒绝 / 去 tz / UTC 再去 tz）。

### drop — commit 边界启发式数字恢复

- **原因**: 与 typed SSOT 及 sheetbook r6 冲突；源 change 已从根去掉 stringify。
- **状态**: 拒绝；勿 reopen，除非推翻 typed 主线（需治理级讨论）。

---

## Branch Options（已关闭）

| 选项 | 状态 | 说明 |
|---|---|---|
| 双字段 CSV+tabular 旁路 | 否决 | 终态为物化 typed segment |
| 文档迁移到 `xlsx_memory`+`export_xlsx` 代替修 `xlsx_file` | 否决为框架答案 | 可作用户临时 workaround |
| 无条件恢复 `to_csv_artifact()` 急切副本 | 否决 | 与 intermediate-store r2 冲突；用「按 consumer 显式派生」代替 |

---

## Risk Analysis（相对源 change 终态）

| ID | 风险 | 可能性 | 影响 | 本 change 缓解 | 残留 / 升级条件 |
|---|---|---|---|---|---|
| R1 | 外部依赖「xlsx_file 全是 str cell」的后处理失效或双重转换 | 中 | 中 | proposal Impact 标明 bugfix；MVP 对照 | 发布说明提醒去掉 `_post_process_workbook` 数字修复 |
| R2 | write 时物化使 workbook plan 常驻全量 rows，大报表峰值上升 | 中 | 中 | 与 sheetbook 同模型；去掉急切 CSV 副本部分对冲 | 若峰值不可接受 → 另案流式/分段 commit（非本 future 默认） |
| R3 | `book_sheet_rows(xlsx_file)` 可见性/截断与 sheetbook 漂移 | 中 | 高 | design 要求同契约；tasks 含可见性单测 | 用户报告不一致 → 立即 reopen 源 change 或 hotfix |
| R4 | 同一 output 双消费（xlsx + csv）缺 CSV artifact | 低（当前少见） | 高 | 本 change **有意不实现**自动派生；见上条 later | 触发「按 consumer 显式派生」升格为 change |
| R5 | `resolve_workflow_input_csv` 误用于 ROWS-only output | 中 | 高 | write 路由改 tabular；legacy workbook 一并改 | 回归测：无 csv map 时 xlsx write 成功、csv resolve fail-fast 清晰 |
| R6 | Decimal / bool / None 在 openpyxl 边界表现与预期不符 | 低 | 中 | 管道保 `FieldValue`；文件 round-trip 不承诺（对齐 sheetbook r7） | 文档写清；MVP 覆盖 Decimal/None/bool |
| R7 | 仅改 kind 未改 `OutputSpec.format` 导致 sink 路径歧义 | 低 | 高 | design/tasks 强制整段进入 `format=excel` | code review 检查点 |
| R8 | workbook/sheetbook 模块双份实现后续漂移 | 中 | 中 | 数据模型先对齐 | 升格「合并模块」later |
| R9 | 公开工具 `in_memory_rows_to_in_memory_csv` 被误当作「应自动调用」 | 低 | 低 | design 写明显式工具；collect 不急切调用 | 文档/注释强调；派生逻辑进独立 change |

### 风险结论

- **阻断实现**: 无（R4 为已知范围外缺口，用 future 预案承接）。
- **实现期必测**: R3、R5、R6、R7。
- **发布期必宣**: R1。
- **升格 future→change**: 优先看 R4 是否出现真实双消费。

---

## Triggers to Reopen（源 change 或本 future）

1. `book_sheet_rows(xlsx_file)` 可见性/截断与 sheetbook 不一致（→ 源 change hotfix 或 follow-up fix change）。
2. 出现「单 output → xlsx + csv」双消费缺 CSV（→ 升格「按 consumer 显式派生」）。
3. 有人提议恢复无条件 `to_csv_artifact()`（→ **拒绝**，引导至显式派生方案）。

---

## Traceability

| 字段 | 值 |
|---|---|
| Source change | `llmanspec/changes/c5-xlsx-file-numeric-type-loss/` |
| Design anchor | Collect § `in_memory_rows_to_in_memory_csv` 显式工具 / 不急切 |
| Spec anchors | shared-output r24；managed-temp-outputs r1（typed SSOT）；intermediate-store r2/r7 |
