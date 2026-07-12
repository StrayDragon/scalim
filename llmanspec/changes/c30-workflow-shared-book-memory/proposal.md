---
depends_on:
  - c20-book-write-policy-python-ssot
blocks: []
---

# c30-workflow-shared-book-memory

## Why

共享 book 的安全模型（多节点写入 → 内存 plan 累积 → 成功后一次 openpyxl commit）**没有** openpyxl 并发损坏问题，但有明确性能代价：

- apply 时物化全量 typed segments 进 plan（`workflow-shared-output-containers` r25）
- demand artifact 与 plan 可能双驻留
- 失败则前面物化白做

`llmanspec/futures/xlsx-file-numeric-type-loss/future.md` **R2** 已记录该峰值风险。  
`notplan/c1-streaming-xlsx-output` 解决的是 **demand 宽表 ColumnExcelSink** 另一层问题，且草案把 streaming knobs 放进 YAML——与「YAML 只编排」方向冲突，本 change **不**采纳 YAML streaming 配置。

本 change 依赖上游 `book-write-policy-python-ssot`：budget / 释放相关调参必须走 Python policy，不得回流 YAML。

进度追踪：仓库根 `_HANDOFF.md`。

## What Changes

### P0（本 change MUST）

- write node 消费完 workflow-managed ROWS/artifact 后，按最终消费者规则**尽早释放** demand 侧内存副本（避免与 plan segments 无必要双驻留）
- commit/discard 后释放 plan 持有的 segment 行数据（降低尾峰）
- 可观测：关键释放点可诊断（事件或既有 diagnostics；不引入 YAML 开关）

### P1（本 change MUST，依赖上游 policy API）

- `BookBudgetPolicy`（Python）对 `xlsx_memory`（及 design 约定是否覆盖 `xlsx_file`）生效；超限 fail-fast
- 文档标明：budget 不再出现在 YAML

### P2+（本 change 可列为后续 tasks / future，不阻塞归档）

- 分段 spill 到 staging 再拼装（降低峰值，保留成功后一次 publish）
- sheet seal（写满不可再 append）等更强约束
- **不做**默认边写边 openpyxl（破坏原子 discard）；若未来要做，必须独立 change + 显式 profile

### 明确不做

- 不把 flush/streaming 配置加入 YAML `outputs.write`
- 不实现 futures「非托管 bypass 立即落盘」作为默认路径
- 不与 `c1-streaming-xlsx-output` 混为同一 PR（可在 HANDOFF 挂「另案 reframe 到 Python」）

## Capabilities

### Modified Capabilities

- `workflow-shared-output-containers` — 释放时机、预算来自 runtime policy、峰值约束
- `workflow-sheetbook-resources` — budget 来源改为 Python policy
- `yaml-dsl-runtime-policy-boundary` — 明确内存/释放类 knobs 仅 Python（与上游对齐的补充）

## Impact

- **代码区域**: `src/scalim/workflow/resources*.py`、`write_nodes.py`、`artifacts`/`execute_controller` 释放路径、tests
- **破坏性**: 行为上默认仍一次 publish；若更积极释放导致「写后仍持有 artifact 引用」的误用方失败，视为修正
- **依赖**: **depends_on** `book-write-policy-python-ssot`

## Examples

### YAML（不变的瘦编排）

```yaml
workflow:
  resources:
    books:
      report:
        xlsx_memory:
          export_xlsx:
            path: ./out
  runs:
    - id: a
      demand: ./a.yaml
    - id: b
      demand: ./b.yaml
```

### Python（budget + 未来 profile 挂点示意）

```python
result = run_workflow(
    "workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(...),
        # resources_policy=ResourcesPolicy(books={
        #     "report": BookResourcePolicy(
        #         write=BookWritePolicy(mode="append"),
        #         budget=BookBudgetPolicy(max_sheets=8, max_total_cells=1_000_000),
        #     )
        # }),
    ),
)
```
