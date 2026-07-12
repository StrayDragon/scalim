# Tasks: workflow-shared-book-memory

## Propose / 收紧（已完成）

- [x] 0.1 收紧 proposal/design：消除开放选项；P2+ 迁 futures
- [x] 0.2 `llman sdd validate c30-workflow-shared-book-memory --strict --no-interactive --stage spec`
- [x] 0.3 更新 `_HANDOFF.md`（c20 archived；c30 MUST 口径；P2+ → futures）

## Apply（实现时逐项勾选）

- [x] 1.1 P0：实现 consumer closure 判定（write nodes 为 artifact 消费者；`book_sheet_rows` 由 plan 生命周期保证可见性；见 design）
- [x] 1.2 P0：write 成功且无剩余 write consumers → discard demand artifact（既有 refcount + diagnostics）
- [x] 1.3 P0：`commit_all` / `discard_all` 后释放 plan segments
- [x] 1.4 P0：释放点 diagnostics（原因枚举；既有 logging 通道）
- [x] 1.5 P0：回归 — 多 sheet / append / `book_sheet_rows` 可见性不破（既有 coverage + plan 仅尾释放）
- [x] 1.6 P0：释放相关单测（`tests/workflow/test_c30_shared_book_memory.py`）
- [x] 2.1 P1：对拍 `xlsx_memory` + `BookBudgetPolicy` 超限 fail-fast；omit = unlimited
- [x] 2.2 P1：确认 `xlsx_file` **不**执行 cell budget（兼容口径测试）
- [x] 2.3 P1：YAML `xlsx_memory.budget` 仍 fail-fast（c20 回归；既有 validator 测）
- [x] 2.4 文档：workflow 峰值来自 plan 物化；budget/释放仅 Python；链到 futures 后续项
- [x] 3.1 `just llmanspec-check` + 相关 pytest + `just qa`（specs scope-review 已清 c20 遗留 staleness）
- [x] 3.2 归档前：本 tasks 全勾选；`llman sdd validate c30-workflow-shared-book-memory --strict --no-interactive`
