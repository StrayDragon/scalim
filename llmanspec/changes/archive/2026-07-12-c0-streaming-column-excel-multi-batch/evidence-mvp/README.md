# Evidence: multi-batch `set_row_ids` vs hold

结果目录: `.tmp/evidence/streaming-column-excel-multibatch/`（勿提交）

## 固定口径

- hold: `ColumnExcelSink` 全量列再 `close`
- streaming_multibatch: 每窗 `set_row_ids(本窗)` → 写满全部列（本 change）
- streaming_window: 一次 `set_row_ids(全量)` + 按窗 `write_column`（对照）

## 命令

```bash
uv run python llmanspec/changes/archive/2026-07-12-c0-streaming-column-excel-multi-batch/evidence-mvp/repro_multibatch_ab.py \
  --rows 20000 --cols 200 --window-rows 2000
```

## 已记录结果（本地）

| shape | hold peak | window peak | **multibatch peak** | vs hold | vs window |
|---|---:|---:|---:|---:|---:|
| 20k×200 / win=2000 | 0.335GB | 0.259GB | **0.089GB** | ~73% | ~65% |
| 50k×300 / win=2000 | 1.92GB | 0.596GB | **0.108GB** | ~94% | ~82% |
| 100k×300 / win=2000 | 3.59GB | 1.11GB | **0.115GB** | ~97% | ~90% |

- 正确性：`ok=true`（三臂单元格一致）
- 产物：
  - `.tmp/evidence/streaming-column-excel-multibatch/20260712T112310Z/result.json`
  - `.tmp/evidence/streaming-column-excel-multibatch/20260712T112424Z/result.json`
  - `.tmp/evidence/streaming-column-excel-multibatch/20260712T114515Z/result.json`
- 解读：一次 `set_row_ids(全量)` 仍预分配全表 `_pending`/`_values` 壳；**按 batch 追加**只保留当前窗缓冲，peak 更低；随 shape 放大，multibatch 相对 hold/window 的优势更明显。
