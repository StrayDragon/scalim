# 2026-07-13: normalize-xlsx-book-ir-path-presence

> IR / 运行时 book 身份以 **path 有无** 为准（pathful=落盘 workbook；pathless=内存总线 sheetbook）。  
> `BookConfig.kind` / `options.kind` 的 `xlsx_file`/`xlsx_memory` 仅为过渡期 wire shim。  
> YAML 仍可用 deprecated 别名（直至 `c999-remove-deprecated-xlsx-file-memory-kinds`）。

对应 llmanspec change: `llmanspec/changes/c25-normalize-xlsx-book-ir-path-presence/`

上游: `references/upgrades/2026-07-13-unified-xlsx-book-kind.md`
