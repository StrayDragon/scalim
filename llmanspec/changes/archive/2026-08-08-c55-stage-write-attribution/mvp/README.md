# MVP pointer — write attribution (c55)

c55 的可复现对拍与 **c50 obs-demo 同一 harness**（合成矩阵里双节点 `write>0`、`notes.write_stage_attribution=sink_path_timed`）。

## 复现 / evidence

见：

`llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/mvp/`

重点读：

- `evidence/*/profiles/*/run_stats.json` → `stages_total.write`、各 `nodes[].stages_total.write`
- `evidence/*/sampling_matrix.json` → wall tax + CSV equiv

本目录不复制 harness，避免双份漂移。
