# Upgrade: OutputWriteLayout（Python 写出布局 SSOT）

> 日期：2026-08-11  
> 相关 change：`c30-output-write-layout-python-policy`  
> **选型 / 正确性 / 无 auto / 启发式 SSOT**：`docs/doc/getting-started/excel-column-residency.md`  
> Agent 边界与证据表：`references/streaming-column-excel-guidance.md`

## 一句话

文件写出布局用闭集 **`OutputWriteLayout`**（`row_stream` / `column_buffered` / `column_chunked`）在 Python options 显式选型；**禁止 YAML**；未设时由 `streaming`+`excel_column_residency` 推导，默认行为不变。

## 何时读

- 宽表 Excel 峰值 / `column_buffered` vs `column_chunked`
- 用户问「该设 streaming 还是 residency / layout」
- agent 要推荐写出路径调优

## 推荐写法

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, OutputWriteLayout, run

run(
    "demand.yaml",
    options=DemandRunOptions(
        runtime=DemandRunRuntimeOptions(
            output_write_layout=OutputWriteLayout.COLUMN_CHUNKED,
        ),
        # security=...
    ),
)
```

纯 IR：

```python
from scalim.execution import ExecutionRequest, OutputSpec, OutputWriteLayout

ExecutionRequest(
    ...,
    output=OutputSpec(format="excel", path="out.xlsx", streaming=False),
    output_write_layout=OutputWriteLayout.COLUMN_CHUNKED,
)
```

## 迁移窗

| 旧 | 新（推荐） |
|----|------------|
| `excel_column_residency=ExcelColumnResidency.CHUNKED` | `output_write_layout=OutputWriteLayout.COLUMN_CHUNKED` |
| 省略 residency（HOLD） | 省略 layout，或显式 `COLUMN_BUFFERED` |

双写时：**显式 layout 优先**。  
选型表、业务格子等价、百万格启发式、无 auto → **只读人类页**，本卡不复述。

## Agent 硬边界

- MUST NOT 在 YAML 发明 `output_write_layout` / residency / `write.streaming`
- MUST NOT 对 books/composition 建议 `COLUMN_CHUNKED`
- MUST NOT 静默 auto 切 layout；只给可复制的 Python options 改法

## 例子

- Notebook：`notebooks/marimo/example_public_api_suite/chapters/ch162_public_api_output_write_layout.py`
- 双跑证据：`scripts/bench_output_write_layout_dual_run.py --preset medium`
