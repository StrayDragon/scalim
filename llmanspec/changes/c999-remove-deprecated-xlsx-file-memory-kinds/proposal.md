---
depends_on:
  - normalize-xlsx-book-ir-path-presence
blocks: []
---

# remove-deprecated-xlsx-file-memory-kinds

> **DRAFT** — 仅提案占位；下游迁移完成后再补齐 delta specs / tasks / 实施。  
> **不要**把本项再写回 `llmanspec/futures/`（futures 将移除；本 change 为硬删 SSOT）。

## Why

`add-unified-xlsx-book-kind` 已把推荐 authoring 收敛为 `books.<id>.xlsx`（path 可选），并以 **warning** 保留 `xlsx_file` / `xlsx_memory` 别名。`normalize-xlsx-book-ir-path-presence` 完成后，运行时身份也不再依赖假 kind 字符串。

下游（notebooks / skills / 外部仓）迁完后，旧 kind 别名应从 schema、parse、校验与文档中 **BREAKING 硬删**，避免双路径长期并存。

## What Changes（草案）

1. Schema / parse / validator：**拒绝** `resources.books.*.xlsx_file` / `xlsx_memory`（及旧 `export_xlsx` 挂载在 memory 上的别名路径）；错误信息指向 `xlsx` + path 语义与 upgrade 笔记。
2. 删除 deprecated warning 路径与相关兼容测试；保留迁移文案于 archived upgrade 笔记（Before 块仅作历史）。
3. skills / 语法目录 / 示例：只出现 `xlsx`；历史 Before 块可保留在 dated upgrade 笔记中。
4. **前置**：`normalize-xlsx-book-ir-path-presence` 已落地；仓库内推荐示例与 notebooks 已无旧 kind；外部下游迁移窗口关闭。
5. **不做**：删除内存总线语义；合并 workbook/sheetbook 实现模块；把 write/budget 写回 YAML。

## Capabilities（预留）

- `yaml-dsl-books-resources` — BREAKING 移除 deprecated book kind 别名

## Impact

- **破坏性**：是（旧 YAML 直接 fail-fast）
- **迁移**：`xlsx_file:{path}` → `xlsx:{path}`；`xlsx_memory:{}` → `xlsx:{}`；`xlsx_memory.export_xlsx.path` → `xlsx.path`
- **隐私**：示例继续只用虚构 id/path

## Open（补齐提案前）

- [ ] 确认外部下游旧 kind 用量≈0（证据不入库真实路径）
- [ ] 写齐 `specs/` + `tasks.md` + 匿名 `examples/` Before(应失败)/After
- [ ] 与 `refactor-workflow-xlsx-backends-unify`（若并行）划清边界：本 change 只删 YAML/parse 别名
