# Tasks — remove-deprecated-xlsx-file-memory-kinds

> BREAKING 清债。YAML 只留 `xlsx`；Python 工厂名保留；kind wire / observability strip / `RowId*` 一并收敛。  
> Apply 实现项写在文末 Backlog（**非 checkbox**），避免 draft/提案阶段 `--strict` 被未实现项挡住。

## Propose（已完成）

- [x] 扩展 proposal（含保留 `xlsx_file_single_sheet`）/ design / delta / tasks
- [x] delta：`yaml-dsl-books-resources`（硬删别名 + pathful/pathless + 去 kind shim 合约）
- [x] delta：`yaml-dsl-observability-boundary`（observability fail-fast）
- [x] delta：`yaml-dsl-output-overrides`（工厂名稳定）
- [x] delta：`runtime-typedef-aliases`（移除 RowId*）
- [x] delta：`workflow-managed-temp-outputs`（pathful/pathless 表述）
- [x] `llman sdd validate c999-remove-deprecated-xlsx-file-memory-kinds --strict --no-interactive`
- [x] 守卫写明：不重命名工厂；不合并 workbook/sheetbook；write/budget 不回流 YAML；保留 pathless 总线

## Backlog（Apply — 非 checkbox）

1. Schema / parse / validate：移除 `xlsx_file`/`xlsx_memory`；旧分支 fail-fast；删 DeprecationWarning 路径；跑生成器（禁手改 `*.gen.*`）
2. Kind shim 终态：停用 `legacy_kind_shim` 契约；`get_book_kind` 删除或非契约；写节点走 pathful/pathless；测试不再断言旧 kind 字符串
3. 保留 `RunOverrides.xlsx_file_single_sheet` 名与签名；内部改 pathful；其它工厂同理；工厂对拍测
4. Observability：strip+warning → fail-fast；测改 error
5. 删除 `RowId`/`RowIdSeq`/`RowIdList`；`LoaderResult` 改 `BusinessKey`；仓内替换
6. Docs/skills/examples：upgrade 笔记（硬删映射 + 工厂保留）；推荐路径只留 `xlsx`；`just gen-docs`
7. 回归：相关 pytest + `llman sdd validate ... --strict`；再 `llman-sdd-verify` → archive
