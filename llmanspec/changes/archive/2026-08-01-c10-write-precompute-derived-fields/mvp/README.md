# c10 复杂 MVP + 固定基准（C：行+列含链式）

## 用途

在实现引擎晚算 **之前** 固定：

1. **黄金期望值**（`golden_table`）：平坦派生 + 链式 `c0→c1→…`  
2. **当前引擎 eager** 对拍（须 `golden_ok=true`）  
3. **仿真峰值**：行晚算 / 列晚算（含链式中间列暂留）  
4. **回归契约**（写进 `baseline-complex.json`）

实现后：同一参数下引擎输出必须继续命中黄金表；峰值/discard 契约见 JSON 内 `regression_contract`。

## 怎么跑

```bash
# 默认 500 行 × 12 平坦 + 深度 5 链；并写入稳定基准文件名
uv run python llmanspec/changes/c10-write-precompute-derived-fields/mvp/repro_complex_baseline.py \
  --write-baseline

# 更大压力（可选）
uv run python llmanspec/changes/c10-write-precompute-derived-fields/mvp/repro_complex_baseline.py \
  --rows 4000 --flat-fields 40 --chain-depth 8 --write-baseline
```

稳定基准：`mvp/evidence/baseline-complex.json`

## 链式小例子（黄金规则）

```text
v0 → c0 = v0+1 → c1 = c0+1 → … → c_k = v0+(k+1)
另有 d0.. 仅依赖 (v0,v1)，互不依赖
```

列路径晚算+链：写完依赖方之前，中间 late 列须暂留（仿真峰值 ≈ `rows × chain_depth`）。

## 规模矩阵（~5 / ~15 / ~30 GiB 交叉验证）

`run_scale_matrix.py`：按校准 `~64 B/derived-cell` 估 eager 全驻留，覆盖 **flat / chain / mixed × row / column**。

| scale | 含义 |
|-------|------|
| `smoke` | 秒级 sanity + 引擎黄金 |
| `small` / `medium` / `large` | ~5 / ~15 / ~30 GiB **驻留仿真**（宽表） |
| `small_engine` / `medium_engine` / `large_engine` | 对应档位的 **引擎黄金代理**（窄 plan，分钟级） |

```bash
# 全档位仿真 + 交叉校验（单调峰值等）
uv run python llmanspec/changes/c10-write-precompute-derived-fields/mvp/run_scale_matrix.py \
  --scales smoke,small,medium,large --sim-only --write-baseline

# 引擎黄金：smoke + 三档代理
uv run python llmanspec/changes/c10-write-precompute-derived-fields/mvp/run_scale_matrix.py \
  --scales smoke,small_engine,medium_engine,large_engine --engine --write-baseline --allow-rss-gb 28

# 真跑 ~5GiB 引擎（机器内存够时）
uv run python llmanspec/changes/c10-write-precompute-derived-fields/mvp/run_scale_matrix.py \
  --scales small --engine --allow-rss-gb 12
```

稳定基准：

- `evidence/baseline-matrix-smoke-small-medium-large.json`（仿真）
- `evidence/baseline-matrix-smoke-small_engine-medium_engine-large_engine.json`（引擎代理）

## 其它脚本

| 脚本 | 说明 |
|------|------|
| `repro_row_late_vs_eager.py` | 行路径简单对照 |
| `repro_column_late_vs_eager.py` | 列路径简单对照（无链） |
| `repro_complex_baseline.py` | 小规模复杂黄金主基准 |
| `run_scale_matrix.py` | **5/15/30GiB 交叉矩阵** |
