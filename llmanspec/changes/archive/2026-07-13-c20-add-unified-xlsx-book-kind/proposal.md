---
depends_on:
  - c15-decide-xlsx-memory-book-role
blocks: []
---

# add-unified-xlsx-book-kind

## Why

`xlsx_file` / `xlsx_memory` 命名重叠；`export_xlsx` 与 `path` 叠腿。匿名盘点：内存总线语义必须保留；`xlsx_memory`+`export_xlsx` 生产命中 0。

引入统一 YAML identity：`books.<id>.xlsx`（**path 可选**）。旧 kind **warning deprecated** 仍可运行，待下游迁移后再另案移除。

**边界**：YAML 只声明结构/identity；write/budget 等仍 Python policy（对齐 `book-write-policy-python-ssot`）。

## What Changes

1. Schema/parse/compile 支持 `xlsx`；无 path=总线，有 path=版本化落盘；`xlsx` 上禁止 `export_xlsx`。
2. `xlsx_file` / `xlsx_memory` 仍可解析，**必须 warning** + 迁移文案；语义分别等价于有/无 path 的 `xlsx`（旧 `export_xlsx.path`→path）。
3. 测试与匿名 `examples/unified-xlsx/` 锁定 Before/After 与 warning 行为。
4. skills/升级笔记：新示例只用 `xlsx`；标明 Python policy 边界。
5. **不在本 change**：硬删旧 kind；合并 workbook/sheetbook 模块；spill/seal。

## Capabilities

- `yaml-dsl-books-resources` — r13/r14（统一 `xlsx` + deprecated 兼容）

## Impact

- **本阶段**：非硬断（旧 YAML 仍跑 + warning）
- **后续 BREAKING**：`remove-deprecated-xlsx-file-memory-kinds`（名待定）在迁移完成后移除旧实现
- **隐私**：示例/文档禁止外部报告真实 path/业务名
