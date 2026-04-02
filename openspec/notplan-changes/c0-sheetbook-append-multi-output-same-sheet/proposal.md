## Why

在 workflow 场景里,同一个 demand 往往会产出多个 output(例如 summary + details),而用户希望把它们追加到同一个 Excel sheet 里形成“同页多段表格”的报告结构。

目前 `xlsx_memory`(sheetbook) 路径会在第二次写入同一 sheet 时直接报错(duplicate producer)，导致这类报告必须拆分为多个 sheet 或改用其它输出路径,与直觉的 append 语义不一致。

## What Changes

本提案聚焦 workflow 托管写入路径(`workflow.resources.books` + write/append node + sheetbook/workbook)。先把 `xlsx_memory(sheetbook)` 的 append 语义补齐到“多 output 可追加同一 sheet”的直觉行为。

- `xlsx_memory`/sheetbook 的重复写入检测升级粒度:
  - 从 “同一 producer_node_id 不能写同一 sheet 多次”
  - 升级为 “同一 (producer_node_id, input_output_id) 不能写同一 sheet 多次”
  - 含义: 同一 demand 的不同 output 可以写同一 sheet(作为追加段)，但同一个 output 仍不允许重复写入(避免 silent duplication)
- 修复 `book_sheet_rows`/`iter_sheetbook_sheet_rows` 的快照截断语义:
  - 当前按 `ref.node` 找到 **first occurrence** 就截断；依赖 “同一 sheet 中同一 producer 最多出现一次” 的前提
  - 当允许同一 producer 多段写入时,快照 MUST 包含该 producer 在该 sheet 的所有段
  - 因此截断点需要调整为 **last occurrence**(或等价语义),保证快照语义正确
- (实现细节层面的预期) sheetbook segment 结构需要携带 `input_output_id`:
  - 用于重复写入检测/更好的错误信息/确定性排序

### Example

一个常见报告: 同一 demand 产出两个 output,都指向同一 sheet。

```yaml
workflow:
  resources:
    books:
      report:
        kind: xlsx_memory
        export_xlsx: ".tmp/out/report.xlsx"

demands:
  sales_report:
    # ...
    outputs:
      summary:
        to:
          book: report
          sheet: "Sales"
        write:
          mode: append
          header_policy: always

      details:
        to:
          book: report
          sheet: "Sales"
        write:
          mode: append
          header_policy: always
```

现状:
- `summary` 写入后 `details` 触发 `Duplicate sheetbook write for the same producer ...`(因为两者 producer_node_id 相同,都是该 demand run.id)

期望:
- `Sales` sheet 最终内容为两段表格(按 decl_order 追加),并保持确定性输出
- 下游如果使用 `book_sheet_rows(ref.node=<sales_report.run_id>)` 读取快照,必须能读到 `summary + details` 两段(而不是被 first occurrence 截断导致漏段)

非目标(本提案不做):
- “非 workflow 的直接导出 Excel” 路径(`output_composition/ExcelWorkbookSink`)的同 sheet 复用
  - 该路径涉及 sink 生命周期/close 行为/表头策略,需要单独设计,不适合并入本 MVP

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `workflow-sheetbook-resources`: `xlsx_memory(sheetbook)` 允许同一 demand 的多个 outputs 追加写入同一 sheet；重复写入检测提升到 (producer_node_id, input_output_id) 粒度；`book_sheet_rows` 快照在该语义下保持正确(不漏段)。

## Impact

- 影响代码(实现侧):
  - `src/scalim/workflow/resources_sheetbook.py`
    - segment 元数据需要补充 `input_output_id`
    - duplicate 检测逻辑与 `iter_sheetbook_sheet_rows` cutoff 逻辑需要调整
- 风险与边界:
  - 行为变化仅发生在 `xlsx_memory(sheetbook)` + “同一 demand 多 output 指向同一 sheet” 场景；其它场景保持既有 fail-fast/预算护栏/确定性排序语义。
  - 需要补齐快照语义的测试覆盖,否则会引入“读到不完整快照”的隐性错误(比 fail-fast 更难排查)。

