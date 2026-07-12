# Tasks: workflow-shared-book-memory

## Propose 阶段（已完成）

- [x] 0.2 `llman sdd validate c30-workflow-shared-book-memory --strict --no-interactive --stage spec`
- [x] 0.3 写入 `_HANDOFF.md` 依赖关系（depends_on c20）

## Apply 阶段 backlog（实现时改为 checkbox 并逐项勾选；须先落地 c20 policy API）

详见 `_HANDOFF.md` 与本目录 `design.md`。实现清单：

0. 确认 `c20-book-write-policy-python-ssot` policy API 已可联调
1. P0：write 消费后释放无剩余消费者的 demand artifact
2. P0：commit/discard 后释放 plan segments
3. P0：回归多 sheet / append / `book_sheet_rows`
4. P0：释放相关测试
5. P1：接线 `BookBudgetPolicy` → sheetbook（及 design 约定的 workbook）
6. P1：确认 YAML budget 已被上游拒绝
7. P1：超 budget fail-fast；unlimited 缺省
8. 文档：峰值来自 plan 物化；调参在 Python
9. 标注 streaming notplan 需 reframe；可选更新 futures R2
10. `just llmanspec-check` + pytest + `just qa`
11. 归档前：backlog 转 `[x]` 并 full strict validate
