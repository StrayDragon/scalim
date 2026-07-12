# Tasks: book-write-policy-python-ssot

## Propose 阶段（已完成）

- [x] 1.1 完成本 change 下各 capability delta（runtime-policy-boundary / write-policy / books-resources / shared-output / output-overrides）
- [x] 1.2 `llman sdd validate c20-book-write-policy-python-ssot --strict --no-interactive --stage spec`
- [x] 1.3 写入仓库根 `_HANDOFF.md` 并链到本 change

## Apply 阶段 backlog（实现时改为 checkbox 并逐项勾选）

详见 `_HANDOFF.md` 与本目录 `design.md`。实现清单：

1. 新增 typed `BookWritePolicy` / `BookBudgetPolicy` / `ResourcesPolicy`（Enum SSOT 遵守 AGENTS）
2. 挂到 `WorkflowRunOptions`（及必要时 demand 入口）
3. builtin defaults 与今日缺省对拍
4. `resource_defs` / compile 读取 effective Python policy
5. schema 移除 books `write_defaults` 与 `xlsx_memory.budget`；刷新 `*.gen.json`
6. validate/compile：旧字段 fail-fast + 迁移提示
7. 收缩 `RunOverrides.resources` 对 write_defaults/budget 的 overlay
8. 迁移测试 + 文档（workflow.md / capability-matrix / review-checklist / skills）
9. `just llmanspec-check` + 相关 pytest + `just qa`
10. 归档前：将本文件 backlog 转为 `[x]` 勾选并 `llman sdd validate ... --strict`（full）
