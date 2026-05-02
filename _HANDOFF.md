# Handoff: derived-fields userlike evidence bench

这是一套**本地临时**的合成复现基准，用于在不引入业务数据的前提下，复现“字段多、call_by 多、kwargs-only、基本不使用 `$ctx`”的形态，并用 `py-spy` / `memray` 固定归因证据。

## 位置

- 复现脚本：`.tmp/repro/derived_fields_userlike/`
- 证据输出：`.tmp/evidence/derived_fields_userlike/`

> 注意：`.tmp/` 不应提交，也不会随 `git worktree` 自动复制；如需在其它 worktree 使用，请从**主仓库路径**手动拷贝该目录。

## 一条命令固定证据

```bash
python .tmp/repro/derived_fields_userlike/run_evidence.py --scenario student_v3_like --rows 300000 --batch-size 20000
```

产物目录内包含：
- `bench.raw.json`：raw run 的 wall time + shape/环境摘要
- `bench.pyspy_speedscope.json`：`py-spy` 跑出来的 wall time（用于估计 profiler 额外开销）
- `cpu.speedscope.json`：`py-spy record --format speedscope`（若本机有 `py-spy`；默认开启）
- `cpu.svg`：可选（`--pyspy-mode svg` 或 `--pyspy-mode both`）
- `memray.bin` / `memray.flamegraph.html` / `memray.summary.txt`：内存分配证据（默认较小 rows；若本机有 `memray`）

可选参数：
- `--pyspy-mode speedscope|svg|both`（默认 `speedscope`）
- `--no-pyspy` / `--no-memray`

## 场景形态（仅计数）

- `student_v3_like`：base fields `171`、call_by `58`、compute `1`、call_by 中 `$ctx` 使用 `0`
- `cus_collect_like`：base fields `41`、call_by `33`、compute `125`、call_by 中 `$ctx` 使用 `0`
