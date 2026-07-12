# Proposal: streaming-column-excel-multi-batch

## Why

已归档的 `StreamingColumnExcelSink` 在 `set_row_ids` 上 **只允许一次调用**，与 pipeline 列模式「每 batch `set_row_ids(本批)` → 写满本批全部列」不兼容。  
行窗 peak 收益已在证据中验证；本 change 只补 sink 契约，使多 batch 行窗可直接复用同一 sink 实例。

## What Changes

1. `StreamingColumnExcelSink.set_row_ids` **MAY 多次调用**：追加新 `row_id`（对齐 `ColumnExcelSink` 的 extend 语义）
2. 首次调用打开 `write_only` workbook；后续调用只扩展 `_pending`/`_values`/`_row_index`
3. 重复 `row_id` MUST fail-fast
4. **非目标**: pipeline/YAML 自动选用 Streaming；改默认 `ColumnExcelSink`；`on_source_complete` 钩子

## Capabilities

### Modified Capabilities

- `output-sink-contracts` — Streaming sink 多 batch `set_row_ids` 追加语义

## Impact

- **破坏性**: 极小 — 原先「第二次 `set_row_ids` 必抛」的行为变为允许追加；仅影响依赖该错误的调用方（测试曾锁定 once）
- **关联**: futures R2 residual；archive `2026-07-12-c0-streaming-column-excel-sink`
- **ethics.risk_level**: low
- **ethics.prohibited_actions**: 不引入 YAML streaming；不改默认 ColumnExcelSink
