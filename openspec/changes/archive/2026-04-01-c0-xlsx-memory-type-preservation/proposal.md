## Why

在假设 `c0-xlsx-memory-internal-field-headers` 已落地的前提下,`xlsx_memory` 的下一个核心问题不再是“键名是否纯化”,而是“值类型是否仍被错误地字符串化”。

当前 `workflow-managed artifact -> sheetbook -> book_sheet_rows` 链路会把内部值压扁为 `str`,带来两类问题:

- 语义错误: `int` / `Decimal` / `bool` / `None` 的内部契约被破坏,用户被迫在下游补 `_auto_cast` 之类的猜测性恢复逻辑
- 性能瓶颈: 对 `xlsx_memory` 这类 workflow 内部 in-memory 数据管道而言,先字符串化、再在下游恢复,本身就是不必要的热点开销

对非结束节点的 workflow 内部链路来说,如果用户选择 `in memory` 路径,系统应尽量保留原本基础类型,尤其不能把上游已经产出的 `Decimal` 再降级成字符串后做后置恢复。换言之,`xlsx_memory` 应当是 typed internal container,而不是“带导出能力的字符串表”。

## What Changes

- 在不新增 book kind 的前提下,将现有 `xlsx_memory` 升级为 typed internal semantics:
  - 内部 sheetbook rows 保留 `FieldValue` 值域
  - `book_sheet_rows` 默认返回保留原始基础类型的 rows
  - 仅在最终 `export_xlsx` commit/export 边界执行面向 spreadsheet 的序列化/转义
- 将 workflow-managed temp outputs 中,供 `xlsx_memory` 写节点消费的中间态从 `CSV` 等价字符串化语义升级为显式 typed runtime artifact contract:
  - `xlsx_memory` 路径以 per-output typed artifact 为 SSOT
  - 若同一 output 仍需服务 `CSV` 等价 consumer,系统 MAY 按需派生字符串 artifact
- 保持 `xlsx_memory` 的现有 DSL surface:
  - 不新增 typed book kind
  - 不新增 `typed: true` 之类的 opt-in 参数
  - 不改变 `xlsx_file` / `csv_file` 的既有行为
- 明确本次 change 的空值边界:
  - 真实 `None` 在 typed path 中必须被保留
  - 不引入基于空串的猜测性 `\"\" -> None` 恢复规则
  - 本 change 只约束“值进入 runtime 后如何在 `xlsx_memory` internal path 中保真传输”; `compute/call_by` 如何安全地产生 `Decimal` 由独立的 `yaml-compute-decimal` change 负责

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `workflow-sheetbook-resources`: 将 `xlsx_memory` 定义为 typed internal sheetbook,内部 rows 与 `book_sheet_rows` 返回值必须保留 `FieldValue` 类型域。
- `workflow-managed-temp-outputs`: 对供 `xlsx_memory` 写节点消费的 workflow-managed 中间态,要求以 per-output typed artifact 作为显式 runtime contract,避免 `CSV` 等价字符串化热点路径。
- `yaml-dsl-books-resources`: 明确 `books.kind=xlsx_memory` 与 `^workflow/book_sheet_rows` 的用户可见契约是“canonical field key + preserved FieldValue values”,而不是“canonical key + stringified values”。

## Impact

- 受影响代码主要包括 `src/scalim/workflow/resources_sheetbook.py`, `src/scalim/workflow/execute.py`, `src/scalim/execution/contracts.py`, `src/scalim/execution/run_ir.py`, `src/scalim/execution/output_composition.py`, `src/scalim/sinks/_internal/rows.py`, `src/scalim/sinks/_internal/sink_csv.py`。
- 受影响规范包括 `openspec/specs/workflow-sheetbook-resources/spec.md`, `openspec/specs/workflow-managed-temp-outputs/spec.md`, `openspec/specs/yaml-dsl-books-resources/spec.md`。
- 这是现有 `xlsx_memory` 语义的一次一步到位升级,不是兼容式双轨设计。任何依赖“`book_sheet_rows` 返回字符串 row”并在下游手动恢复类型的 workflow,都需要迁移到直接消费 typed rows。
- 当前 SSOT 为本 change 下的 OpenSpec 工件与主 specs; 若 docs/spec indexes 或 injected blocks 需要刷新,应运行 `just gen-docs`,而不是手改生成物。共享前需运行 `just openspec-check`。
