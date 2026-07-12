# Evidence: StreamingColumnExcelSink vs ColumnExcelSink

结果目录: `.tmp/evidence/streaming-column-excel-ab/`（勿提交）

## 固定 MVP（仅本目录，不进 `src/scalim/`）

- 类: `MvpStreamingColumnExcel`（`repro_streaming_ab.py`）
- 语义: 行字段齐备 → `write_only` append → 释放行缓冲
- 写出模式: **行窗**（每窗写满全部列，才能在过程中释放；全列顺序写满全部行无法降峰）

## 命令

```bash
# 正确性 + 效果（默认 20k×200，window=2000）
uv run python llmanspec/changes/c0-streaming-column-excel-sink/evidence-mvp/repro_streaming_ab.py \
  --rows 20000 --cols 200 --window-rows 2000
```

## 门槛

- `correctness.ok == true`
- `gate_peak_reduced == true`（streaming peak 相对 hold 降 ≥20% 或绝对值 ≥0.2GB）
