# Upgrade: OutputWriteLayout（Python 写出布局 SSOT）

> 日期：2026-08-11  
> 相关 change：`c30-output-write-layout-python-policy`  
> 人类文档：`docs/doc/getting-started/excel-column-residency.md`

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

## Agent 硬边界

- MUST NOT 在 YAML 发明 `output_write_layout` / residency / `write.streaming`
- MUST NOT 对 books/composition 建议 WINDOW
- MUST NOT 静默 auto 切 layout（建议见 notplan `c40-output-write-layout-advisory`）

## 例子

- Notebook：`notebooks/marimo/example_public_api_suite/chapters/ch162_public_api_output_write_layout.py`
