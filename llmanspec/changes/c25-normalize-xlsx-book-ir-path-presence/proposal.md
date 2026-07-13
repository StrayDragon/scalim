---
depends_on:
  - add-unified-xlsx-book-kind
blocks:
  - remove-deprecated-xlsx-file-memory-kinds
---

# normalize-xlsx-book-ir-path-presence

## Why

`add-unified-xlsx-book-kind` 已把 YAML authoring 收敛为 `books.<id>.xlsx`（path 可选），但内部 `BookConfig.kind` 仍为字符串 `xlsx_file` / `xlsx_memory`，仅为复用 workbook/sheetbook 后端。

这使 IR/调试面继续暴露「假 kind」，与 SSOT「有 path / 无 path」不一致，也拖累后续硬删旧 YAML kind 与后端收敛。

本变更把 **IR / 运行时身份** 归一为 path 是否存在；**不**合并 workbook/sheetbook 实现模块（可另开）。

## What Changes

1. 运行时 book 身份以 **path 有无**（或等价枚举/标志）表达；禁止新代码依赖 `kind in ("xlsx_file","xlsx_memory")` 作为业务分支（迁移期内允许兼容 shim）。
2. YAML 解析结果：统一 `xlsx` 与 deprecated 别名均归一到同一 IR 形状；对外 dump/debug 优先展示 path 语义，而非假 kind 名。
3. 既有 workbook（有 path）/ sheetbook（无 path）后端绑定改为由 path 有无驱动；行为与 `add-unified-xlsx-book-kind` 对齐，不改用户可见落盘/总线语义。
4. 测试：IR 归一、旧 kind 仍可 parse（若尚未删除）、统一 `xlsx` 回归；匿名 `examples/` Before/After 锁定。
5. **不在本 change**：从 YAML schema 硬删 `xlsx_file`/`xlsx_memory`（见 `remove-deprecated-xlsx-file-memory-kinds`）；spill/seal；Python write/budget 政策回 YAML。

## Capabilities

### Modified Capabilities

- `yaml-dsl-books-resources`: IR 身份以 path 有无为准（不再以内部假 kind 字符串为 SSOT）

## Impact

- Affected code: book parse → BookConfig / resources materialize / workbook vs sheetbook 分派
- Affected specs: `yaml-dsl-books-resources`
- Downstream: 解锁硬删旧 YAML kind（`remove-deprecated-xlsx-file-memory-kinds`）
