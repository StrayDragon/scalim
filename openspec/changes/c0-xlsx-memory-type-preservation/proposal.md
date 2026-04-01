## Why

`xlsx_memory` 当前除 header 语义泄漏外,还存在更深层的问题: 内部值在 workflow-managed artifact → sheetbook → `book_sheet_rows` 链路中被字符串化,导致 `int` / `Decimal` / `bool` 等原生值类型丢失。对内部数据管道而言,这会进一步影响 `normalize.index_by_key`、relation lookup、聚合结果复用与类型稳定性。

这一问题与 header 纯化相关,但不适合并入当前 `c0-xlsx-memory-internal-field-headers`。header change 的目标是先把“内部键空间”和“结果展示”彻底切开; 类型保留则会触及中间 artifact 形态、sheetbook 存储模型、读取契约与潜在新 kind 设计,范围更大,需要单独调研。

## What Changes

- 以 draft proposal 形式单独调研 `xlsx_memory` / workflow-managed 中间态的值类型保留问题。
- 对比现有字符串化链路、`InMemoryRows` 现有 typed 基础设施、以及可能的 typed sheetbook / sidecar / 新 kind 方案。
- 明确后续 change 应该修改哪些内部契约,以及是否需要新增能力或升级现有 `xlsx_memory` 行为。
- 本 proposal 当前不承诺实现,不创建 specs/design/tasks,仅作为后续调研与决策入口。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `workflow-sheetbook-resources`: 评估 `xlsx_memory` 是否需要在内部存储与 `book_sheet_rows` 读取时保留原生 `FieldValue` 类型域。
- `workflow-managed-temp-outputs`: 评估 workflow-managed 中间 artifact 是否应从 `CSV` 等价字符串化语义升级为 typed intermediate 语义。

## Impact

- 受影响代码可能包括 `src/scalim/sinks/_internal/sink_csv.py`, `src/scalim/sinks/_internal/rows.py`, `src/scalim/workflow/resources_sheetbook.py`, `src/scalim/workflow/execute.py`, `src/scalim/execution/output_composition.py`。
- 受影响规范可能包括 `openspec/specs/workflow-sheetbook-resources/spec.md`, `openspec/specs/workflow-managed-temp-outputs/spec.md`, 以及视方案而定的 `yaml-dsl-books-resources`。
- 当前 SSOT 仅为此 proposal 与后续对应 OpenSpec 工件; 暂不涉及生成文档或 injected blocks。若后续需要同步 docs/spec indexes,应通过 `just gen-docs` 与 `just openspec-check` 完成验证,而非手改生成物。
