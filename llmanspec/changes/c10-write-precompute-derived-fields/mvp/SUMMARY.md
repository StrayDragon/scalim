# 复杂基准摘要（决策 C）

## 小规模复杂黄金

```bash
uv run python llmanspec/changes/c10-write-precompute-derived-fields/mvp/repro_complex_baseline.py --write-baseline
```

默认：`rows=500`，`flat_fields=12`，`chain_depth=5` → `evidence/baseline-complex.json`（row/column `golden_ok`）。

## 规模矩阵（5 / 15 / 30 GiB）

| 层 | 命令要点 | 结果文件 |
|----|----------|----------|
| 驻留仿真 | `--scales smoke,small,medium,large --sim-only` | `baseline-matrix-smoke-small-medium-large.json` |
| 引擎黄金代理 | `--scales smoke,small_engine,… --engine` | `baseline-matrix-smoke-small_engine-…json` |
| **~5GiB 真跑引擎** | `--scales small --engine --allow-rss-gb 12` | `baseline-matrix-small.json`（6/6 `golden_ok`；discard sink 下峰值 RSS≪估驻留） |

仿真交叉校验（24 case）：eager 峰值随档位单调不降；row late = 一行派生数；column late ≈ `rows×chain`。示例量级：

| scale | flat 例（rows×fields） | est eager |
|-------|------------------------|-----------|
| small | ~52k × 1600 | ~5 GiB |
| medium | ~105k × 2400 | ~15 GiB |
| large | ~157k × 3200 | ~30 GiB |

引擎代理用窄 plan（`width_mode=engine`）验证 flat/chain/mixed × row/column 黄金；真 ·5/15/30· GiB 引擎需 `--allow-rss-gb` 与足够宿主机内存。

实现晚算后：同参 `golden_ok`；`fast_fail` discard。
