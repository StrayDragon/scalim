# 2026-07-13: normalize-xlsx-book-ir-path-presence

## 变更摘要

IR / 运行时 book 身份以 **path 有无** 为准：

- **pathful**（有版本化导出 `path`）→ 落盘 workbook 后端
- **pathless**（无 `path`）→ 内存总线 sheetbook 后端

`BookConfig.kind` / `options.kind` 的 `xlsx_file` / `xlsx_memory` 仅为过渡期 wire shim；compile 会额外发出 `options.pathful`。  
YAML authoring 仍推荐统一 `xlsx`（见上游）；旧别名可用至 `c999-remove-deprecated-xlsx-file-memory-kinds` 硬删。

本批次 **不**合并 workbook/sheetbook 源文件；**不**从 YAML 硬删旧别名。

对应 llmanspec change: `llmanspec/changes/archive/2026-07-13-c25-normalize-xlsx-book-ir-path-presence/`

上游: `references/upgrades/2026-07-13-unified-xlsx-book-kind.md`

## Migration Checklist

### 1) YAML authoring

无需为“身份正规化”改 YAML；优先仍按 `2026-07-13-unified-xlsx-book-kind.md` 迁到 `xlsx`（可选 `path`）。

### 2) 依赖 `options.kind` / `get_book_kind` 的内部/工具代码

- 新 SSOT：看 `options.pathful` 或 resource defs 成员关系（workbook vs sheetbook）
- `get_book_kind` 仍返回 deprecated shim 字符串（`xlsx_file`/`xlsx_memory`），勿再当作长期身份

### 3) 下游仓库

对新 YAML 用 `xlsx`；旧 kind 仅作过渡。硬删窗口见 draft change `c999-remove-deprecated-xlsx-file-memory-kinds`。
