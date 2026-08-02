# StreamingColumnExcelSink / ExcelColumnResidency

完整选型与边界见:

- 人类文档: `docs/doc/getting-started/excel-column-residency.md`
- yaml-dsl skill: `agentdev/skills/scalim-yaml-dsl/references/streaming-column-excel-guidance.md`

## 策略速查

| 策略 | API | 何时启用 |
|---|---|---|
| `HOLD`（默认） | 省略或 `ExcelColumnResidency.HOLD` | 普通列式 Excel；峰值可接受 |
| `WINDOW` | `DemandRunRuntimeOptions` / `ExecutionRequest.excel_column_residency` | 宽表列式 IR（`streaming=False`）、无 composition、要砍 peak |
| 手写 sink | `StreamingColumnExcelSink` | 自管行窗写出 |
| YAML books | （无 residency） | 已是行 sink；**不要**设 WINDOW |

```python
from scalim.execution import ExcelColumnResidency, ExecutionRequest, OutputSpec

ExecutionRequest(
    export_layout=...,
    output=OutputSpec(format="excel", path="out.xlsx", streaming=False),
    excel_column_residency=ExcelColumnResidency.WINDOW,
)
```

`WINDOW` + `output_composition` / `streaming=True` → fail-fast。

## 与 0.10 row-wise fusion

列式 Excel sink(含 `WINDOW` / `HOLD` 的 column path)属于 fusion **安全外壳排除项**:该路径下不会做同 deps 行内融合。选型 WINDOW 时不要期望 fusion 墙钟收益;fusion 对拍见 `docs/doc/releases/rowwise-fusion-0.10.md`。
