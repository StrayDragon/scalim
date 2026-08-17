# StreamingColumnExcelSink / OutputWriteLayout

完整选型与边界见人类页 SSOT：

- `docs/doc/getting-started/excel-column-residency.md`
- yaml-dsl skill: `agentdev/skills/scalim-yaml-dsl/references/streaming-column-excel-guidance.md`

## 策略速查（推荐 API）

| 策略 | API | 何时启用 |
|---|---|---|
| 默认（不设） | 省略 `output_write_layout` | 与历史一致：由 `streaming`+`excel_column_residency` 推导 |
| `row_stream` | `OutputWriteLayout.ROW_STREAM` | 行式文件 sink（CSV/Excel streaming） |
| `column_buffered` | `OutputWriteLayout.COLUMN_BUFFERED` | 列式整表缓冲到 close；峰可接受 |
| `column_chunked` | `OutputWriteLayout.COLUMN_CHUNKED` | 宽表列式 IR Excel、无 composition、要砍 peak |
| 手写 sink | `StreamingColumnExcelSink` | 自管行窗写出 |
| YAML books | （无 layout 字段） | 已是行 sink；**不要**设 `COLUMN_*` |

```python
from scalim.execution import ExecutionRequest, OutputSpec, OutputWriteLayout
# 或: from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions, OutputWriteLayout

ExecutionRequest(
    export_layout=...,
    output=OutputSpec(format="excel", path="out.xlsx", streaming=False),
    output_write_layout=OutputWriteLayout.COLUMN_CHUNKED,
)
```

迁移窗：`excel_column_residency=ExcelColumnResidency.CHUNKED` 在**未设** layout 时仍推导为 `column_chunked`。

`COLUMN_CHUNKED` / `ExcelColumnResidency.CHUNKED` + `output_composition` → fail-fast；CSV + `COLUMN_CHUNKED` → fail-fast。  
无 auto / 启发式 / 业务格子等价 → 人类页，勿在此展开。

## 与 0.10 row-wise fusion

列式 Excel sink（含 `column_buffered` / `column_chunked` 的 column path）属于 fusion **安全外壳排除项**:该路径下不会做同 deps 行内融合。选型 `column_chunked` 时不要期望 fusion 墙钟收益;fusion 对拍见 `docs/doc/releases/rowwise-fusion-0.10.md`。
