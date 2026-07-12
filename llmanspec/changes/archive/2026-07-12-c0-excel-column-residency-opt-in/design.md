# Design: excel-column-residency-opt-in

## 产品词汇（统一叙事，两域适用）

| Layout | 今日谁在用 | residency 是否生效 |
|---|---|---|
| `ROW_STREAMING` | YAML books / `output_composition` | **N/A**；设 `WINDOW` → fail-fast |
| `COLUMN_HOLD` | IR `excel` + `streaming=False` 默认 | `HOLD` |
| `COLUMN_WINDOW` | 同左 + opt-in | `WINDOW` → `StreamingColumnExcelSink` |

手写 `ExecutionRequest.sink=StreamingColumnExcelSink(...)` 仍优先于工厂（既有行为）。

## 为何不挂 `ResourcesPolicy`

`BookWritePolicy` 管 book 容器（sheet/append/header/budget）。  
列式文件 sink 驻留是 **IR 文件写出**语义，挂 books 会误导“YAML books 可切 WINDOW”。

## 调用示意（审查用；apply 时落代码）

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, run
from scalim.dsl.yaml_dsl import ExcelColumnResidency  # 或 sinks / execution 导出面另定

run(
    "demand.yaml",  # 仅当该 demand 走 IR 列式单文件、无 composition 时 WINDOW 才生效
    options=DemandRunOptions(
        runtime=DemandRunRuntimeOptions(
            excel_column_residency=ExcelColumnResidency.WINDOW,
        ),
        # security=...
    ),
)
```

纯 IR：

```python
ExecutionRequest(
    output=OutputSpec(format="excel", path="out.xlsx", streaming=False),
    excel_column_residency=ExcelColumnResidency.WINDOW,
)
```

## Fail-fast 文案要点

当 `output_composition is not None` 且 `excel_column_residency == WINDOW`：

> YAML/组合输出为行流式写出；`ExcelColumnResidency.WINDOW` 仅适用于列式 IR 文件 sink（`streaming=False`）。请去掉 WINDOW，或改用手写 `StreamingColumnExcelSink` / 非 composition 列式路径。

## 非目标

- YAML `outputs.write` / books 增加 layout/streaming 字段
- RouterColumnSink / 多 sheet column / shared-book Streaming
- 默认改为 WINDOW
