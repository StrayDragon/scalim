# Tasks: streaming-column-excel-multi-batch

## 1. Sink

- [x] 1.1 `StreamingColumnExcelSink.set_row_ids` 支持追加；首次开簿；重复 pk fail-fast
- [x] 1.2 更新类 docstring（多 batch 行窗）

## 2. Tests / docs

- [x] 2.1 多 batch `set_row_ids` + 写满列 对拍 `ColumnExcelSink`
- [x] 2.2 重复 `row_id` / 替换原「只允许一次」测试
- [x] 2.3 futures R2 residual：append 已落地；pipeline opt-in 仍 later

## 3. Validate

- [x] 3.1 `llman sdd validate c0-streaming-column-excel-multi-batch --strict --no-interactive`
- [x] 3.2 相关 pytest + `just qa`（或等效子集）
