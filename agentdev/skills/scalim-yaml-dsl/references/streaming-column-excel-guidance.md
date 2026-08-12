# StreamingColumnExcelSink：框架路径边界与建议

> 给 agent / 维护者的排错与选型指南。  
> **选型 / 正确性 / 无 auto / 启发式 SSOT（人类页）**: `docs/doc/getting-started/excel-column-residency.md`  
> Upgrade 卡: `references/upgrades/2026-08-11-output-write-layout.md`  
> 证据归档: `llmanspec/changes/archive/2026-07-12-c0-streaming-column-excel-sink/`、`.../c0-streaming-column-excel-multi-batch/`、`.../c0-excel-column-residency-opt-in/`。

本文只保留 **agent 硬边界、工厂锚点、证据表**；何时启用 HOLD/WINDOW、入口矩阵、业务格子等价、百万格启发式 → **只读人类页**，勿在此复述。

## 三条路径（速查）

| 路径 | 实际 sink | 与 `COLUMN_WINDOW` |
|---|---|---|
| **YAML / workflow books** | 行 `ExcelSink` / workbook sheet | **无效**；列布局 + composition → **fail-fast** |
| **IR 列式 `COLUMN_HOLD`（默认）** | `ColumnExcelSink` | 默认，勿改除非有证据 |
| **IR 列式 `COLUMN_WINDOW`（opt-in）** | `StreamingColumnExcelSink` | 推荐 API；迁移窗：`ExcelColumnResidency.WINDOW` |

工厂: `src/scalim/execution/run_ir.py` → `_create_file_sink`（按 effective `OutputWriteLayout`）。  
Enum: `scalim.execution.OutputWriteLayout`（推荐）；迁移窗 `ExcelColumnResidency`；均可从 `scalim.dsl.yaml_dsl` 导入。

```python
from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions, OutputWriteLayout

DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.COLUMN_WINDOW)
# 迁移窗等价（未设 layout）: excel_column_residency=ExcelColumnResidency.WINDOW
```

## 与 0.10 row-wise fusion

列 sink 路径(含 `HOLD`/`WINDOW`)在 fusion 安全外壳内 **不融合**。宽表峰值用 WINDOW 砍 RSS 与 fusion 墙钟收益是正交问题;不要混谈。总览:`references/0.10-release-highlights.md`。

## Agent 硬边界

1. **MUST NOT** 发明 YAML `write.streaming` / residency / layout 字段
2. YAML Excel 峰值 ≠ 缺 WINDOW；先说明行 sink 路径
3. 推荐 `COLUMN_WINDOW` 前确认是列式 IR（`streaming=False`、无 composition）——细则见人类页 §2
4. shared-book **不能**插 StreamingColumn
5. **MUST NOT** 假装有 auto / run_stats hint；只给显式 Python options（人类页 §3）

## 证据口径

| shape | hold peak / 比 | WINDOW | 备注 |
|---|---:|---:|---|
| 100k×300（归档） | ~3.59GB | **~0.12GB**（~97%） | 多 batch WINDOW |
| m_20k_50（medium 双跑） | RSS H/W **2.46×** | — | 墙钟 W/H ≈1.02；行数相等 |
| m_50k_50 | **4.87×** | — | 同上 |
| m_20k_100 | **3.54×** | — | 同上 |

校准入口：`uv run python scripts/bench_output_write_layout_dual_run.py --preset medium`（产物在 `.tmp/`，勿提交）。  
通俗页：`llmanspec/notplan/c40-output-write-layout-advisory/research/write-layout-advisory-explainer.html`。
