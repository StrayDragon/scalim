# Tasks: streaming-column-excel-sink

## 1. 规划与证据 MVP

- [x] 1.1 proposal / design / delta
- [x] 1.2 固定证据 MVP（行窗 + `MvpStreamingColumnExcel`，不进生产代码）
- [x] 1.3 `evidence-mvp/repro_streaming_ab.py`
- [x] 1.4 `llman sdd validate c0-streaming-column-excel-sink --strict --no-interactive`

## 后续（apply 阶段）

- 跑通 evidence 并记录 result.json 结论
- 迁入生产 `StreamingColumnExcelSink` + 单测
- archive / `just qa`
