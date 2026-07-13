# Tasks — decide-xlsx-memory-book-role

> 本 change 以 **draft + review** 为主；默认不改 `src/`。  
> Review 后可选工作写在文末「Backlog」（非 checkbox，避免 draft 校验被未实现项挡住）。

## Draft 落地（已完成）

- [x] delta `yaml-dsl-books-resources` r12 + scenarios
- [x] `llman sdd validate c15-decide-xlsx-memory-book-role --strict --no-interactive`
- [x] 工件无外部报告真实 path / 业务名（proposal/design/examples 扫过）
- [x] `examples/in-memory-bus/` Before/After 虚构同构示例
- [x] `futures/xlsx-file-numeric-type-loss/future.md`：产品 keep 由本 change 承接；实现合并仍 later；拒绝默认 deprecate memory kind

## 守卫（本 change 范围）

- [x] 不修改 `resources_workbook` / `resources_sheetbook` 行为（本 draft 无 src 改动）
- [x] 不在本 change apply 全量 backend unify

## Backlog（review 后另议；非本 draft 门禁）

- review：`examples/in-memory-bus/` 是否足以说明「总线 vs 落盘书」
- 可选：skills `task-workflow-authoring` 补「何时用 memory / file」+ 指向本 examples（仍虚构名）
- 可选：站内 docs 一句心智模型（手工 SSOT；禁止手改 `.gen.`）
- 若改口 rename/deprecate：另开 BREAKING change，不在本 change 默默改 authoring
