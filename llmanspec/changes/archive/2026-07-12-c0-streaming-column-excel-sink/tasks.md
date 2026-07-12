# Tasks: streaming-column-excel-sink

## 1. 规划与证据

- [x] 1.1 proposal / design / delta
- [x] 1.2 证据脚本 + 20k/50k/100k×300 行窗 A/B
- [x] 1.3 `llman sdd validate`（规划阶段）

## 2. 实现

- [x] 2.1 `StreamingColumnExcelSink`（`sinks/_internal/streaming_column_excel.py`）
- [x] 2.2 导出 `scalim.sinks` / `api`
- [x] 2.3 单测 `tests/sinks/test_streaming_column_excel_sink.py`
- [x] 2.4 evidence 脚本改用生产 sink

## 3. 验收

- [x] 3.1 `llman sdd validate c0-streaming-column-excel-sink --strict --no-interactive`
- [x] 3.2 archive
