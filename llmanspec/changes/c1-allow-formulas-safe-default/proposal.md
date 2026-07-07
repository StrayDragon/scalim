# Proposal: allow-formulas-safe-default

## Why

所有 CSV/Excel sink（`CSVSink`、`ColumnCSVSink`、`BlockColumnCSVSink`、`ExcelSink` 等）的 `allow_formulas` **默认为 True**。当数据来自不受信任的 loader（如外部数据库）时，以 `=`、`+`、`-`、`@` 开头的值会原样写入 CSV/Excel，在用户打开文件时可能触发公式注入攻击。

注意：仓库中已有 archived change `2026-04-29-allow-formulas-default-true` 明确将默认值设为 `True`。本 change 建议**反转**该决策或提供更安全的默认配置。

## What Changes

1. **将 sink 构造函数的 `allow_formulas` 默认值改为 `False`**（安全默认）
2. **在 YAML DSL schema 中将 `allow_formulas` 默认值改为 `false`**
3. **更新文档**：说明何时需要显式设置 `allow_formulas: true`（仅在数据完全可信时）
4. **迁移指南**：告知现有用户若需保持原有行为需显式设置 `allow_formulas: true`

**BREAKING**: 现有未显式设置 `allow_formulas` 的配置行为会变化。

## Capabilities

### Modified Capabilities

- `output-sink-contracts` — 默认值变更
- `yaml-dsl-file-resources` — schema 默认值变更
- `yaml-dsl-books-resources` — workbook 默认值变更

## Impact

- **代码区域**: `src/scalim/sinks/_internal/sink_csv.py`, `src/scalim/sinks/_internal/excel.py`, DSL schema
- **破坏性**: **BREAKING** — 现有未显式设置 `allow_formulas` 的管道输出值会被转义
- **安全**: 公式注入风险从 Medium 降为 Low
