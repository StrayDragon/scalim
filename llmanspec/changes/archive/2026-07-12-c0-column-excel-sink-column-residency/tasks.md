# Tasks: column-excel-sink-column-residency

## 1. 证据

- [x] 1.1 `evidence-mvp/repro_column_residency_ab.py`（hold vs chunk_release）
- [x] 1.2 30k×300 取证：peak 无收益 → 定案 A

## 2. 规范与文档

- [x] 2.1 更新 `ColumnExcelSink` / `IColumnSink` 文档字符串，明确源列可丢、sink 副本驻留至 close
- [x] 2.2 delta `output-sink-contracts` r10
- [x] 2.3 `llman sdd validate c0-column-excel-sink-column-residency --strict --no-interactive`

## 3. 验收

- [x] 3.1 相关 sinks 文档/回归测试仍通过
- [x] 3.2 `just qa`（或至少 sinks + llmanspec-check）
