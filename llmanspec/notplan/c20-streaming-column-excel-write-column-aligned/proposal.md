# Proposal: streaming-column-excel write_column_aligned

> 一句话描述: 为 `StreamingColumnExcelSink` 补齐 `write_column_aligned`，与 pipeline 列模式 prefer-aligned 对称，避免 WINDOW 路径上多余的 `dict(zip)`。

> **状态（2026-08-11）**：主路径已实现；本壳记录动机与验收，供归档引用。

## Why

列模式 pipeline 在 `SupportsWriteColumnAligned` 时走 aligned；`StreamingColumnExcelSink`（WINDOW）此前只有 `write_column(Mapping)`，导致工厂/路径仍先 `dict(zip(row_ids, values))`。相对 WINDOW 的 GB 级降峰这是次要 MB 级分配，但是对称缺口。

## What Changes

- `StreamingColumnExcelSink.write_column_aligned(field_key, row_ids, values)`：按 zip 填窗并 flush；长度不一致 fail-fast。
- 与 `write_column` 共享 `_write_field_at_row`；值等价 + 多 batch 行为不变。
- 测试：aligned vs dict 产物相等；len mismatch。

## Impact

- 不增峰；不改默认 HOLD；YAML books 仍行式。
- ROI：每批每列少一次中间 dict（相对 WINDOW 主收益为次要）。
