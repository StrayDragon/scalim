# Tasks — normalize-xlsx-book-ir-path-presence

> 本 change **提案已齐**（proposal / design / delta）；实现待 apply。  
> 实现清单写在文末「Backlog」（**非 checkbox**，避免未 apply 时挡住 `validate --strict`）。

## 0. 规划工件

- [x] proposal / design / delta `yaml-dsl-books-resources` r15 + scenarios
- [x] depends_on：`add-unified-xlsx-book-kind`；blocks：`remove-deprecated-xlsx-file-memory-kinds`
- [x] future 已指向本 change（IR path-presence）；硬删旧 kind 指向 c999 draft（不写回 futures）
- [x] `llman sdd validate c25-normalize-xlsx-book-ir-path-presence --no-interactive`（提案态）；apply 完成后补 `--strict` 全绿

## Backlog（apply 时勾选；非本提案门禁）

1. 定义 book 身份为 path 有无（或等价枚举），替换 `BookConfig.kind` 字符串作为 SSOT
2. parse/compile：`xlsx` 与 deprecated 别名均归一到同一 IR
3. materialize：按 path 有无绑定现有 workbook/sheetbook 后端
4. 回归统一 `xlsx`（有/无 path）行为不变
5. 若旧 kind 仍可 parse：断言归一后 IR，而非长期保留假 kind
6. 匿名 `examples/` Before/After（可选，与 c20 示例对齐说明）
7. 升级笔记：IR = path 语义；旧 kind 仅 YAML 兼容层（直至硬删案）
8. `just llmanspec-check` / 相关单测通过
