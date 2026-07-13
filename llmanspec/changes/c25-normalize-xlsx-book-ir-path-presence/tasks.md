# Tasks — normalize-xlsx-book-ir-path-presence

> 实现任务（可验证）。身份 SSOT = path 有无；`kind` 仅 wire shim。

## 0. 规划工件

- [x] proposal / design / delta `yaml-dsl-books-resources` r15 + scenarios
- [x] depends_on：`add-unified-xlsx-book-kind`；blocks：`remove-deprecated-xlsx-file-memory-kinds`
- [x] future 已指向本 change（IR path-presence）；硬删旧 kind 指向 c999 draft（不写回 futures）

## 1. IR / parse 归一

- [x] 1.1 定义 book 身份为 path 有无（`book_identity.is_pathful_book`），`kind` 仅 legacy shim
- [x] 1.2 parse/compile：`xlsx` 与 deprecated 别名归一后按 path 分派；options 发 `pathful` + kind shim
- [x] 1.3 materialize：`resource_defs` 按 `pathful`（回退 legacy kind）绑定 workbook/sheetbook

## 2. 测试与示例

- [x] 2.1 回归统一 `xlsx`（有/无 path）行为不变（c20 测）
- [x] 2.2 IR 断言改为 path / pathful（`tests/yaml_dsl/test_c25_xlsx_book_ir_path_presence.py`）
- [x] 2.3 匿名 examples：沿用 c20 archive 示例形状（本 change 不另开）

## 3. 文档 / skills

- [x] 3.1 升级笔记：`references/upgrades/2026-07-13-normalize-xlsx-book-ir-path-presence.md`
- [x] 3.2 `llman sdd validate c25-normalize-xlsx-book-ir-path-presence --strict --no-interactive` / 相关单测通过
