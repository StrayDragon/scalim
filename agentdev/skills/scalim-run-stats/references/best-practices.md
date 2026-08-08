# Best practices: Scalim run_stats / low-drift observability

面向 Agent：装配、读数、对拍、排错的默认做法。人类长文见 `docs/doc/viz/run-stats.md`。

## 默认选择

| 场景 | Profile | 说明 |
|------|--------|------|
| 生产 | 不装配 / `BASELINE` | 默认静默；零观测税 |
| 日常自我观测 / CI A/B | `BENCH` | lite 事件；本机 mid ~**+2%** wall；stress 税可淹没在噪声里 |
| 看 stage 内存趋势 | `BENCH_PLUS` | 需 psutil；mid ~**+3%** |
| 短窗深挖 relation / field top-N / viz | `DEBUG` | mid ~**+40%**；必有 `UserWarning`；跑完立刻改回 bench |
| 临时 cardinality probe | demo `probe` 或自建 env | 不要当长期默认 |

## 读数面（最易踩坑）

1. **workflow**：只信 `stats["nodes"]`（及顶层聚合）。禁止用共享 `PerformanceObserver.metrics` 末态当全图。
2. **write**：订阅 `STAGE_SPAN` 后 `stages_total.write` / 每节点 `stages_total.write` 应反映真实 sink I/O；`notes.write_stage_attribution == "sink_path_timed"`。
3. **stage 之和 ≠ 墙钟**：STAGE_SPAN 只覆盖计时窗；workflow/xlsx/close 等仍在 wall 里。用 stage 比相对热点，用 wall 比对拍税。
4. **xlsx vs CSV**：输出等价以 **CSV 内容哈希**为准；workbook 字节常因元数据漂移。

## 装配最佳实践

1. **一份 `built`，共享 `components` 实例**挂到 workflow 各 demand（经 `DemandRunRuntimeOptions`），才能跨 demand 累加 `nodes[]`。
2. **对拍最小集**：`BASELINE` + `BENCH`，同输入，记录 `(bench_wall/baseline_wall)-1` 与 CSV digest。
3. **落盘**：`write_run_stats_sibling(dir, stats)`；可与 viz run 目录同旁路。**禁止**嵌入 `viz_snapshot.json`。
4. **memory**：需要 peak 才 `include_memory=True` / `BENCH_PLUS`；无 psutil 应 fail-fast，不要吞掉。
5. **高影响面**：程序化开 relation / field_compute top-N / viz_trace|full 会 warn——Agent 应在回复里复述警告并建议改 bench。
6. **meta**：`build_run_stats(meta=built["meta"])` 带上 `profile`，避免事后分不清税从哪来。

## 验证清单（Agent 交付前）

- [ ] `schema == "scalim_run_stats/v1"`
- [ ] workflow：`node_count` / `len(nodes)` ≥ 实际 pipeline 数；首节点 loaders 在后续 demand 后仍非空
- [ ] 有写出时：`stages_total.write > 0`
- [ ] baseline↔bench：CSV digest 相等
- [ ] 若开了 debug：文案含观测税警告与 bench 替代
- [ ] 未把完整 run_stats 写入 viz snapshot

## 合成矩阵参考（本机 `.tmp/obs-demo`，非 SLA）

- mid 200k：bench **+2.1%**，bench_plus **+3.3%**，debug **+41%**，CSV equiv 全绿，双节点 `write>0`
- stress 1M：bench ≈ baseline（噪声内），`write≈7s`，CSV equiv 绿

复现：`.tmp/obs-demo/README.md`。
