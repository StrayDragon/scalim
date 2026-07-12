# Evidence: StreamingColumnExcelSink vs ColumnExcelSink

结果目录: `.tmp/evidence/streaming-column-excel-ab/`（勿提交）

## 固定口径

- hold: `ColumnExcelSink` 全量列再 `close`
- streaming_window: 生产 `StreamingColumnExcelSink` + **行窗**（每窗写满全部列）

## 命令

```bash
uv run python llmanspec/changes/archive/2026-07-12-c0-streaming-column-excel-sink/evidence-mvp/repro_streaming_ab.py \
  --rows 20000 --cols 200 --window-rows 2000
```

## 已记录结果（本地）

| shape | hold peak | stream peak | reduction |
|---|---:|---:|---:|
| 20k×200 | 0.35GB | 0.26GB | ~26% |
| 50k×300 | 1.80GB | 0.60GB | ~67% |
| 100k×300 | 3.58GB | 1.11GB | ~69% |
