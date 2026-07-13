# Tasks — add-unified-xlsx-book-kind

> 实现任务（可验证）。YAML = identity/结构；write/budget **不得**回流 YAML。  
> 验收命令写在各节；整包：`llman sdd validate c20-add-unified-xlsx-book-kind --strict --no-interactive`。

## 0. 规划工件

- [x] proposal / design（含别名初衷 + 可维护性/内存优先序）/ delta / 匿名 examples
- [x] delta 复核：add r13/r14；modify r1/r3/r9/r10（消除「仅允许 xlsx_file|xlsx_memory」与统一 `xlsx` 冲突）；scenarios 覆盖别名 warning 与 `export_xlsx`→path
- [x] future 已完成项清理，并指向本 change
- [x] `llman sdd validate c20-add-unified-xlsx-book-kind --strict --no-interactive`（实现中非 strict；**全部任务勾选后**必须 strict 绿）

## 1. Schema / SSOT（YAML identity only）

- [x] schema SSOT 增加 `books.*.xlsx`（`path` optional；`allow_formulas` optional bool）
- [x] `xlsx` mapping **拒绝** `export_xlsx` / `write_defaults` / `budget`（与现有 books 禁令一致）
- [x] 旧 `xlsx_file` / `xlsx_memory` 仍在 schema 中可解析（过渡），文档标注 deprecated
- [x] 跑生成器（`just gen-docs` 或项目既定 schema gen 入口），**禁止手改** `*.gen.*`
- [x] **验收**: schema-only 装载 `examples/unified-xlsx/after.workflow.yaml` 通过；在 `xlsx` 下写入 `export_xlsx` 的最小夹具 fail-fast

## 2. Parse / Validate — deprecated **warning**（硬要求）

- [x] 解析 `xlsx` → 内部模型（有 path / 无 path）
- [x] 解析 `xlsx_file` / `xlsx_memory` → 同一内部模型；**MUST** 产生 warning（稳定文案含迁移到 `xlsx` 的示例片段）
- [x] 旧 `xlsx_memory.export_xlsx.path` → 正规化为有 path，并 warning（提示改 `xlsx.path`）
- [x] 使用旧 kind 时 **MUST NOT** 仅因 deprecated 而 error
- [x] **验收（测试边界）**:
  - 新 `xlsx` 无 path / 有 path：0 deprecated warning
  - 仅 `xlsx_file`：≥1 warning，run/validate 仍成功
  - 仅 `xlsx_memory: {}`：≥1 warning，总线语义仍可测
  - `xlsx` + `export_xlsx`：error（非 warning）
  - 断言 warning 文案含 `xlsx` 与 `path` 迁移关键词（稳定子串 SSOT 放测试常量）

## 3. Compile / Runtime 正规化（不合并后端文件）

- [x] compile 将 `xlsx`/旧 kind 正规化为现有资源 defs（有 path→workbook 路径；无 path→sheetbook defs）
- [x] `book_sheet_rows` 对无 path 与有 path 书均保持可见性合约（对拍匿名 MVP 形状）
- [x] 有 path：commit/publish 版本化语义不变
- [x] 无 path：无导出文件；下游可读 plan
- [x] **验收**: 集成测覆盖 `examples/unified-xlsx/` 同构（可复制到 `tests/` 脱敏夹具）；Before 旧 kind 跑通且有 warning；After 新 kind 跑通且无该类 warning

## 4. Python policy 边界护栏

- [x] 确认 `xlsx` 书仍只通过 `ResourcesPolicy` / `BookWritePolicy` / `BookBudgetPolicy` 配 write/budget（无 YAML 回流）
- [x] **验收**: YAML 写 `write_defaults` 或 `budget` 于任意 book 分支（含 `xlsx`）→ 既有 fail-fast 仍在；单测或既有测不回归

## 5. Docs / skills（生成边界清晰）

- [x] 新增 upgrade 笔记（`agentdev/skills/scalim-yaml-dsl/references/upgrades/`）：Before/After + deprecated warning 说明 + 「参数在 Python」
- [x] `task-workflow-authoring`（或等价）改为推荐 `xlsx`；旧 kind 标 deprecated
- [x] 若需站内页：只改手工 SSOT，再 `just gen-docs`；**不手改** `.gen.` / AUTOGEN 块
- [x] **验收**: `just gen-docs`（若本 change 触发生成）无 drift；笔记可被 `rg` 搜到 `xlsx_file` deprecated / `books.*.xlsx`

## 6. 明确不做（本 change 守卫 — 用测试或 review 勾选）

- [x] 无 PR 删除 `xlsx_file`/`xlsx_memory` 解析路径（硬删属 follow-up BREAKING）
- [x] 无 PR 合并 `resources_workbook.py`/`resources_sheetbook.py` 为单模块
- [x] 无 YAML knobs 控制 warning 开关 / spill / seal

## 7. Follow-up（不在本 tasks 勾选实现）

- 新 change：下游迁移完成后 **移除**旧 kind 与旧 export 路径（warning→error→delete）
- future：`refactor-workflow-xlsx-backends-unify` / spill — 仍 later
