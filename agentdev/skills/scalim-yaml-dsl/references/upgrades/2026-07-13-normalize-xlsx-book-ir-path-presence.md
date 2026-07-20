# 2026-07-13: normalize-xlsx-book-ir-path-presence

> **状态（2026-07-20）**：YAML 旧别名与 `get_book_kind` / `options.kind` wire shim 已由 `2026-07-20-remove-deprecated-xlsx-file-memory-kinds` **硬删/移除**。下文保留本批次落地时的过渡描述，仅作历史迁移上下文；当前 authoring/身份 SSOT 以 2026-07-20 笔记为准。

## 变更摘要

IR / 运行时 book 身份以 **path 有无** 为准：

- **pathful**（有版本化导出 `path`）→ 落盘 workbook 后端
- **pathless**（无 `path`）→ 内存总线 sheetbook 后端

（本批次当时）`BookConfig.kind` / `options.kind` 的 `xlsx_file` / `xlsx_memory` 仅为过渡期 wire shim；compile 会额外发出 `options.pathful`。  
YAML authoring 推荐统一 `xlsx`（见上游）；旧别名硬删见后续 `c999`。

本批次 **不**合并 workbook/sheetbook 源文件；**不**从 YAML 硬删旧别名（硬删属 follow-up）。

对应 llmanspec change: `llmanspec/changes/archive/2026-07-13-c25-normalize-xlsx-book-ir-path-presence/`

上游: `references/upgrades/2026-07-13-unified-xlsx-book-kind.md`  
下游硬删: `references/upgrades/2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md`

## Migration Checklist

### 1) YAML authoring

优先按 `2026-07-13-unified-xlsx-book-kind.md` / `2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md` 使用唯一 `xlsx`（可选 `path`）。

### 2) 依赖 `options.kind` / `get_book_kind` 的内部/工具代码

- SSOT：看 `options.pathful` 或 resource defs 成员关系（workbook vs sheetbook）
- `get_book_kind` / kind wire shim **已移除**（2026-07-20）

### 3) 下游仓库

YAML 只用 `xlsx`；旧别名会 fail-fast。
