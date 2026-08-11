# StreamingColumnExcelSink / OutputWriteLayout

完整选型与边界见:

- 人类文档: `docs/doc/getting-started/excel-column-residency.md`
- yaml-dsl skill: `agentdev/skills/scalim-yaml-dsl/references/streaming-column-excel-guidance.md`

## 策略速查（推荐新 API）

| 策略 | API | 何时启用 |
|---|---|---|
| 默认（不设） | 省略 `output_write_layout` | 与历史一致：由 `streaming`+`excel_column_residency` 推导 |
| `row_stream` | `OutputWriteLayout.ROW_STREAM` | 行式文件 sink（CSV/Excel streaming） |
| `column_hold` | `OutputWriteLayout.COLUMN_HOLD` | 列式缓存到 close；峰可接受 |
| `column_window` | `OutputWriteLayout.COLUMN_WINDOW` | 宽表列式 IR Excel、无 composition、要砍 peak |
| 手写 sink | `StreamingColumnExcelSink` | 自管行窗写出 |
| YAML books | （无 layout 字段） | 已是行 sink；**不要**设 `COLUMN_*` |

```python
from scalim.execution import ExecutionRequest, OutputSpec, OutputWriteLayout
# 或: from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions, OutputWriteLayout

ExecutionRequest(
    export_layout=...,
    output=OutputSpec(format="excel", path="out.xlsx", streaming=False),
    output_write_layout=OutputWriteLayout.COLUMN_WINDOW,
)

# Demand YAML 入口:
# DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.COLUMN_WINDOW)
```

迁移窗：`excel_column_residency=ExcelColumnResidency.WINDOW` 在**未设** layout 时仍推导为 `column_window`。

`COLUMN_WINDOW` / 旧 `WINDOW` + `output_composition` → fail-fast；CSV + `COLUMN_WINDOW` → fail-fast。

**无自动切换**：按数据形状由调用方显式选；观测建议见 notplan `c40-output-write-layout-advisory`。

## 与 0.10 row-wise fusion

列式 Excel sink(含 `WINDOW` / `HOLD` 的 column path)属于 fusion **安全外壳排除项**:该路径下不会做同 deps 行内融合。选型 WINDOW 时不要期望 fusion 墙钟收益;fusion 对拍见 `docs/doc/releases/rowwise-fusion-0.10.md`。
