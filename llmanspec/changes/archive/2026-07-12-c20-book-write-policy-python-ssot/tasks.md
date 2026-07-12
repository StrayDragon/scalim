# Tasks: book-write-policy-python-ssot

## Propose 阶段（已完成）

- [x] 1.1 完成本 change 下各 capability delta（runtime-policy-boundary / write-policy / books-resources / shared-output / output-overrides）
- [x] 1.2 `llman sdd validate c20-book-write-policy-python-ssot --strict --no-interactive --stage spec`
- [x] 1.3 写入仓库根 `_HANDOFF.md` 并链到本 change

## Apply 阶段（已完成）

- [x] 2.1 新增 typed `BookWritePolicy` / `BookBudgetPolicy` / `ResourcesPolicy`（Enum SSOT 遵守 AGENTS）
- [x] 2.2 挂到 `WorkflowRunOptions` 与 `DemandRunOptions.resources_policy`
- [x] 2.3 builtin defaults 与今日缺省对拍（省略 policy = sheet/once/...；budget unlimited）
- [x] 2.4 `resource_defs` / compile 读取 effective Python policy；demand 路径 materialize
- [x] 2.5 schema 移除 books `write_defaults` 与 `xlsx_memory.budget`；刷新 `*.gen.json`
- [x] 2.6 validate/compile：旧字段 fail-fast + 迁移提示
- [x] 2.7 收缩 `RunOverrides.resources` 对 write_defaults/budget 的 overlay
- [x] 2.8 迁移测试 + 文档（workflow.md / capability-matrix / review-checklist / notebooks）
- [x] 2.9 清理死代码（loader/workflow 旧 parse helpers；resource_override 旧 overlay helpers）并收敛覆盖测
- [x] 2.10 刷新 public-api skill / `public-api.gen.md`（导出面）
- [x] 2.11 `just llmanspec-check` + 相关 pytest（`tests/yaml_dsl` + `tests/workflow`）+ schema/docs/public-api drift

## Archive 前（非 apply checkbox；归档时执行）

1. `llman sdd validate c20-book-write-policy-python-ssot --strict --no-interactive`（full）
2. ~~按需 `just qa` 全量门禁~~（已通过：lint/type/coverage/llmanspec/frontend/examples）
3. 归档并合并 specs 后刷新/删除 `_HANDOFF.md`
