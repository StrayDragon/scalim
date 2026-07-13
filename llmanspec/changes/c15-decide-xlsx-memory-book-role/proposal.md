---
depends_on: []
blocks: []
---

# decide-xlsx-memory-book-role

## Why

YAML 上 `xlsx_file` 与 `xlsx_memory` 都是「多 sheet 的 book」，体感容易重叠，引发「能否只留 `xlsx_file`」的产品疑问。

经匿名化外部用量盘点（2026-07-13，证据不入库、不写真实路径/业务名）：

- `xlsx_file` 是多数落盘报表路径
- 至少存在一类生产模式：`xlsx_memory` **无 `export_xlsx`**，多 demand 写入中间 sheet，下游用 `book_sheet_rows` 交叉读取——**内存总线**，不是「少写一个 path 的 xlsx_file」
- 盘点建议：**keep** 双 kind；合并/删除会破坏该模式并引入不必要落盘

本 change 把该产品结论写成可 review 的 draft 合约 + **匿名 YAML MVP**，便于前后对照。实现（文档/skills/是否后续 rename）留待 review 勾选。

来源：`llmanspec/futures/xlsx-file-numeric-type-loss/future.md`（双后端质量债与产品去留需先分清）。

## What Changes

1. **产品结论（本 change SSOT）**：保留 `xlsx_memory` 与 `xlsx_file` 双 kind；不以「file 也能多 sheet」为由折叠 memory。
2. **合约澄清**：`yaml-dsl-books-resources` 增加要求——无 `export_xlsx` 的 `xlsx_memory` 仍是合法内存共享 book（可被 `book_sheet_rows` 消费）。
3. **匿名 MVP 示例**：`examples/in-memory-bus/` 展示 Before（误以为 memory 多余）/ After（明确总线 vs 落盘书）对照；示例 id/路径均为虚构。
4. **明确不做（本 draft）**：不改 runtime 行为；不 rename kind；不合并 workbook/sheetbook 模块；不根据真实用户仓路径写任何文档。

## Capabilities

### Modified Capabilities

- `yaml-dsl-books-resources` — 明确 no-export `xlsx_memory` 内存总线为支持模式

## Impact

- **破坏性**：无（合约澄清 + 示例；默认不改代码）
- **隐私**：提案/示例/tasks **禁止**写入外部报告中的路径、模块名、业务名；仅保留匿名同构形状
- **后续**：
  - authoring 统一：`add-unified-xlsx-book-kind`（`c20-…`）用 `xlsx`+可选 path 承接本 change 的总线语义，旧 kind deprecated
  - 代码层 `refactor-workflow-xlsx-backends-unify` 仍 later（实现债 ≠ 产品删总线）
