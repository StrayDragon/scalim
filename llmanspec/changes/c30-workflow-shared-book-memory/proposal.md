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

`llmanspec/futures/xlsx-file-numeric-type-loss/future.md` **R2** 记录该峰值风险。本 change 是 R2 的第一刀：**尽早释放双驻留 + 验收 `xlsx_memory` 的 Python budget 护栏**。  
更大的 spill / 流式 / seal 等不在本 change（见 futures）。

依赖上游已归档的 `book-write-policy-python-ssot`：budget authoring 已在 Python；本 change **不得**把 budget/释放 knobs 回流 YAML。

进度追踪：仓库根 `_HANDOFF.md`。

## What Changes

全部 MUST；无开放选项。

### 1) Demand artifact 尽早释放

- **消费者定义（封闭）**：对某个 workflow-managed tabular artifact，仅统计仍待执行的 **workflow write nodes**（将该 artifact 作为输入写入 book）
- **不计入**：调用方在 workflow 结束后自行持有的 Python 引用；`CaptureRows` 等非 workflow-managed 路径；`book_sheet_rows`（读 plan，不读 demand artifact）
- **时机**：当某 write node **成功**将 artifact 物化进 book plan，且按上表该 artifact **已无剩余 write consumers**时，系统 MUST 释放 demand 侧内存副本（例如 `artifacts.discard` / 等价）
- **语义**：`book_sheet_rows` 可见性由 **plan** 生命周期保证（见 §2），MUST NOT 因释放 demand artifact 而破坏

### 2) Plan segments 尾释放

- 在 `commit_all` **成功**或 `discard_all` **完成**之后，系统 MUST 释放 book plan 持有的 segment 行数据（清空 segments 和/或丢弃 plan），以降低尾峰
- 释放 MUST 发生在资源生命周期收尾路径上（与现有 `resource_lifecycle` 对齐），不得依赖 YAML 开关
- 在此之前 MUST NOT 清空 plan（保证仍待执行的 `book_sheet_rows` 可读）

### 3) 可观测性（单一口径）

- 关键释放点 MUST 通过 **既有 diagnostics / 结构化日志** 可诊断（至少记录：artifact/book id、释放原因：`no_remaining_consumers` | `commit` | `discard`）
- MUST NOT 新增 YAML 开关；MUST NOT 以本 change 强制引入新的公开 Event 类型（若现有通道不足，仅扩展内部 diagnostics 字段）

### 4) `xlsx_memory` budget 验收（Python only）

- `BookBudgetPolicy` 对 **`xlsx_memory` MUST 强制执行**（超 `max_sheets` / `max_total_cells` fail-fast）
- 未提供 budget policy（或 `as_options_mapping()` 为 `None`）时 MUST 视为 **unlimited**
- YAML `xlsx_memory.budget` MUST 继续被拒绝（上游 c20 已落地；本 change 补测试/文档残留即可）
- **`xlsx_file`：本 change MUST NOT 引入 cell/sheet budget**（保持历史 unlimited）。若未来需要，另开 future/change

## 明确不做（不进 tasks）

- 分段 spill 到 staging 再拼装
- sheet seal（写满不可再 append）
- 默认边写边 openpyxl（破坏原子 discard）
- 将 streaming/flush/budget/release「积极程度」knobs 写入 YAML（含 `outputs.write`）
- 给 `xlsx_file` 套与 `xlsx_memory` 相同的 cell budget
- 与 `notplan/c1-streaming-xlsx-output` 混为同一实现 PR（另案 reframe 到 Python/profile）

上述迁出条目见：`llmanspec/futures/xlsx-file-numeric-type-loss/future.md`（Deferred — shared-book 后续）。

## Capabilities

### Modified Capabilities

- `workflow-shared-output-containers` — 明确释放时机与消费者闭包；budget 对 xlsx_memory 的强制口径
- `workflow-sheetbook-resources` — budget 仅 Python；unlimited 缺省
- `yaml-dsl-runtime-policy-boundary` — 共享 book 释放/budget knobs 不得回流 YAML

## Impact

- **代码区域**: `src/scalim/workflow/`（artifacts、write_nodes、resource_lifecycle、resources_sheetbook）、compile 接线对拍、tests、少量文档
- **破坏性**: 默认仍一次 publish；写后仍假定 demand artifact 常驻的误用 MUST fail 或读到已释放状态——视为修正非法持有，不提供兼容层
- **依赖**: depends_on `book-write-policy-python-ssot`（已归档）

## Examples

### YAML（瘦编排；无 budget）

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
      depends_on: [a]
```

### Python（可选 budget；仅 xlsx_memory 生效）

```python
result = run_workflow(
    "workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(...),
        resources_policy=ResourcesPolicy(
            books={
                "report": BookResourcePolicy(
                    budget=BookBudgetPolicy(max_sheets=8, max_total_cells=1_000_000),
                )
            }
        ),
    ),
)
```
