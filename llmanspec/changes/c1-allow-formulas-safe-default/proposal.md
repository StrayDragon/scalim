# Proposal: allow-formulas-safe-default

## 与 c20/c30 关系

- **不被取代**。`c20` 明确 **暂留 `allow_formulas` 在 YAML**（通常不动态改）；本 change 只翻转默认值 true→false，不把该字段迁出 YAML。
- 同碰 `yaml-dsl-books-resources` schema：apply 顺序建议先保证字段仍在 authoring 面，再改默认值，避免与 c20 削 `write_defaults`/`budget` 的 schema 改动搅在一起。
- 进度总览：仓库根 `_HANDOFF.md`。

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
