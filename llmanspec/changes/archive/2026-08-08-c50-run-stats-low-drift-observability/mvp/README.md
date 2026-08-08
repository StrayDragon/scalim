# MVP：obs-demo 合成矩阵（c50）

可复现的 **profile 墙钟税 / write 归因 / CSV 等价** 采样 harness。工作负载是合成数据，不绑定业务路径。

c55（write stage 归因）与同一矩阵交叉验证；指针见 sibling archive 的 `mvp/README.md`。

## 一句话结论（本机 evidence，非 SLA）

| scale | baseline wall | bench tax | bench_plus | debug | CSV equiv | write |
|-------|---------------|-----------|------------|-------|-----------|-------|
| mid 200k | ~26.5s | **+2.1%** | **+3.3%** | **+41%** | OK | 双节点 `write>0` |
| stress 1M | （见 evidence） | ~**0% ± 噪声** | （通常跳过） | （通常跳过） | OK | `stages_total.write≈7s` |

**Agent 判断**：日常 `BENCH`；`DEBUG` 仅短窗，接受高税与 `UserWarning`。

## 复现

```bash
# 仓库根目录
uv run python llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/mvp/run_obs_demo.py --scale mid
uv run python llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/mvp/run_obs_demo.py --scale stress --profiles baseline,bench
```

默认写出：`.tmp/obs-demo/runs/<scale>_<ts>/`（JSON；`work/` 指纹后删除，便于之后 scalim-viz 观测）。

## 目录

| 路径 | 用途 |
|------|------|
| `run_obs_demo.py` | 入口 |
| `obs_demo_pkg/` | loaders / profiles / collect |
| `workload/` | 合成 workflow YAML |
| `evidence/` | 已钉住的 slim JSON（无 `batches[]` 膨胀；路径已 scrub） |

> 注：仓库根 `.gitignore` 含全局 `debug/`（Rust）。`evidence/**/profiles/debug/` 已用 `evidence/.gitignore` 反选；若再加同类目录可用 `git add -f`。

## 读数约定

- workflow 真相：`run_stats.nodes`（勿读共享 Perf 末态）
- 输出等价：CSV 内容哈希（xlsx 字节不可靠）
- write：`notes.write_stage_attribution == sink_path_timed` 且 `stages_total.write > 0`

人类文档：`docs/doc/viz/run-stats.md`  
Agent skill：`agentdev/skills/scalim-run-stats/references/best-practices.md`
