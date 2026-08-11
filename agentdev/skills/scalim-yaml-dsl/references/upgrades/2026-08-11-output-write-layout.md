# Upgrade: OutputWriteLayout（Python 写出布局 SSOT）

> 日期：2026-08-11  
> 相关 change：`c30-output-write-layout-python-policy`  
> 人类文档：`docs/doc/getting-started/excel-column-residency.md`  
> Agent 详解：`references/streaming-column-excel-guidance.md`

## 一句话

文件写出布局用闭集 **`OutputWriteLayout`**（`row_stream` / `column_hold` / `column_window`）在 Python options 显式选型；**禁止 YAML**；未设时由 `streaming`+`excel_column_residency` 推导，默认行为不变。

## 何时读

- 宽表 Excel 峰值 / HOLD vs WINDOW
- 用户问「该设 streaming 还是 residency」
- agent 要推荐写出路径调优

## 推荐写法

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, OutputWriteLayout, run

run(
    "demand.yaml",
    options=DemandRunOptions(
        runtime=DemandRunRuntimeOptions(
            output_write_layout=OutputWriteLayout.COLUMN_WINDOW,
        ),
        # security=...
    ),
)
```

纯 IR：

```python
from scalim.execution import ExecutionRequest, OutputWriteLayout

ExecutionRequest(
    ...,
    output=OutputSpec(format="excel", path="out.xlsx", streaming=False),
    output_write_layout=OutputWriteLayout.COLUMN_WINDOW,
)
```

## 迁移窗

| 旧 | 新（推荐） |
|----|------------|
| `excel_column_residency=ExcelColumnResidency.WINDOW` | `output_write_layout=OutputWriteLayout.COLUMN_WINDOW` |
| 省略 residency（HOLD） | 省略 layout，或显式 `COLUMN_HOLD` |

双写时：**显式 layout 优先**。

## 选型（人工，非自动）

| 形状 | 建议 |
|------|------|
| YAML books / 中等报表 | 默认（行流）；不要设 `COLUMN_*` |
| 列式 IR Excel、峰不可接受 | `COLUMN_WINDOW` |
| 要历史列缓存语义 | `COLUMN_HOLD` |
| CSV | 勿设 `COLUMN_WINDOW`（fail-fast） |

**启发式（给人/agent，非运行时 auto）**：列式 IR excel + 当前有效 `column_hold` + `n_fields × n_rows ≳ 1e6`（约百万格）→ 可建议显式 `COLUMN_WINDOW`。更小形状先测峰再决定。

**无 auto / 无 run_stats hint**：不要等系统静默切换；L1 观测建议实现已搁置（notplan `c40-output-write-layout-advisory`）。

## 正确性（改 WINDOW 会不会写错？）

| 维度 | 结论 |
|------|------|
| 合法 IR 列式（`excel` + `streaming=False` + 无 composition + pipeline 按 batch `set_row_ids`） | HOLD↔WINDOW **业务格子等价** |
| xlsx 文件字节 | **不必**相等；对拍用业务列 |
| books / composition / 行式 streaming | **非法** → fail-fast，不是静默假开关 |
| WINDOW 某窗列未写齐就 `close` | **更严**报错（防半截表） |

## 证据（本地双跑，勿提交产物）

| 来源 | 摘要 |
|------|------|
| 归档 100k×300 | HOLD ~3.59GB → WINDOW ~0.12GB |
| medium 双跑（`scripts/bench_output_write_layout_dual_run.py --preset medium`） | RSS H/W ≈ **2.5–4.9×**；墙钟 W/H ≈ **1.02**；行数相等 |
| 通俗说明 | `llmanspec/notplan/c40-output-write-layout-advisory/research/write-layout-advisory-explainer.html` |

## Agent 硬边界

- MUST NOT 在 YAML 发明 `output_write_layout` / residency / `write.streaming`
- MUST NOT 对 books/composition 建议 WINDOW
- MUST NOT 静默 auto 切 layout；只给可复制的 Python options 改法

## 例子

- Notebook：`notebooks/marimo/example_public_api_suite/chapters/ch162_public_api_output_write_layout.py`
