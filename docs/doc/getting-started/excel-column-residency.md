# Excel 列式写出策略（HOLD / WINDOW）

??? note "适用读者"
    - 用 Python IR / `ExecutionRequest` 写宽表 Excel、关心峰值内存的使用方
    - 写 YAML books 报表、误以为有 streaming knobs 的集成方
    - 需要给调用方选型建议的 agent / 维护者

本文说明三条**不同**的 Excel 写出路径，以及何时启用 `ExcelColumnResidency`。

更严的契约以 `llmanspec/specs/output-sink-contracts/` 与 `yaml-dsl-runtime-policy-boundary` 为准。

## 1. 先分清三条路径

| 路径 | 典型入口 | 实际实现 | 峰值特征 |
|---|---|---|---|
| **A. YAML / workflow books** | `resources.books` + `outputs.to` | 组合层强制行写出 → `ExcelSink` / workbook sheet | 行流式；**不是** `ColumnExcelSink` |
| **B. IR 列式 HOLD（默认）** | `OutputSpec(format="excel", streaming=False)` | `ColumnExcelSink` | 列缓存到 `close`；宽表 `pre_close` 可很高 |
| **C. IR 列式 WINDOW（opt-in）** | 同上 + `ExcelColumnResidency.WINDOW` | `StreamingColumnExcelSink` | 按行窗刷盘释放；宽表 peak 可大幅下降 |

证据口径（列 HOLD vs 多 batch WINDOW，100k×300）：hold peak ≈ **3.59GB** → window peak ≈ **0.12GB**（约 97%）。  
产物在本地 `.tmp/evidence/`（勿提交）。

## 2. 策略怎么选

### 推荐默认：`HOLD`

- 列数/行数不大，或机器内存充足
- 需要与历史 `ColumnExcelSink` 行为完全一致
- **不要改默认**；未设置 residency 时即为 `HOLD`

### 何时启用：`WINDOW`

同时满足：

1. 使用 **列式** Excel：`format=excel` 且 `streaming=False`（或框架工厂走该分支）
2. 宽表 / 高行数导致 `pre_close` / peak RSS 不可接受
3. **没有** `output_composition`（不是 YAML books 多输出行组合）

调用示例：

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, ExcelColumnResidency
# 也可: from scalim.execution import ExcelColumnResidency

options = DemandRunOptions(
    runtime=DemandRunRuntimeOptions(
        excel_column_residency=ExcelColumnResidency.WINDOW,
    ),
    # security=...
)
```

或纯 IR：

```python
from scalim.execution import ExcelColumnResidency, ExecutionRequest, OutputSpec

req = ExecutionRequest(
    export_layout=...,
    output=OutputSpec(format="excel", path="out.xlsx", streaming=False),
    excel_column_residency=ExcelColumnResidency.WINDOW,
)
```

pipeline 列模式会每批 `set_row_ids(本批)` 再写满列——与 WINDOW sink 的多 batch 语义对齐。

### 何时不要用 `WINDOW`

| 场景 | 原因 |
|---|---|
| YAML / workflow `resources.books` Excel | 已是行 sink；设 `WINDOW` + composition → **fail-fast**（禁止假开关） |
| `streaming=True` 行式 Excel | `WINDOW` 仅对列式生效；会 **fail-fast** |
| 指望 YAML 里写 streaming knobs | **禁止**；runtime policy 只在 Python |
| shared-book 物化峰值 | 另案（spill 等）；不是本 Enum |
| 一次 `set_row_ids(全量行)` 再按列写 | 仍会预分配全表壳；peak 收益差很多——应 **按 batch 追加** `set_row_ids` |

### 手写 sink

需要完全自管写出时，可直接：

```python
from scalim.sinks import StreamingColumnExcelSink
```

按 batch：`set_row_ids(本批)` → 写满全部列 → `close()`。  
显式传入 `ExecutionRequest.sink=...` 时优先于工厂选择。

## 3. 与 YAML 的关系（重要）

- YAML authoring **没有** `excel_column_residency` / `write.streaming` 字段
- books 路径保持行组合；宽表 YAML 峰值问题请先排查 shared-book / 执行上下文，而不是找本开关
- Python `ResourcesPolicy` / `BookWritePolicy` 只管 book 容器语义，**不要**把列式 residency 挂到 books 上

## 4. 相关链接

- 公共 API：`scalim.execution.ExcelColumnResidency`、`scalim.dsl.yaml_dsl.ExcelColumnResidency`、`scalim.sinks.StreamingColumnExcelSink`
- Agent skill 指引：`agentdev/skills/scalim-yaml-dsl/references/streaming-column-excel-guidance.md`
- 并行调参：[`parallel-modes.md`](../architecture/parallel-modes.md)
- 归档证据：`llmanspec/changes/archive/2026-07-12-c0-streaming-column-excel-sink/`、`.../c0-streaming-column-excel-multi-batch/`、`.../c0-excel-column-residency-opt-in/`
