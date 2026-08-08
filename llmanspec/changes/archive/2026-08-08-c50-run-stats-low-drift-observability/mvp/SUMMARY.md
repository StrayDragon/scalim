# Summary — obs-demo matrix (c50)

- **Why**：debug / relation / field top-N 观测税很大；需要可归档、可复现的 profile 对拍证据，避免只留在 `.tmp`。
- **What**：合成 2-demand workflow；profiles `baseline|bench|bench_plus|debug|probe`；落盘 `run_stats` sibling + sampling matrix。
- **Pinned**：`evidence/mid_20260808_165544/`、`evidence/stress_20260808_165846/`（slim JSON）。
- **Runtime JSON（viz）**：`.tmp/obs-demo/runs/`（不入库；可再跑覆盖）。
- **c55**：同一 harness 验证 sink-path write 归因；见 `../2026-08-08-c55-stage-write-attribution/mvp/`。
