## MODIFIED Requirements

### Requirement: workflow YAML exposes a stable authoring surface for sheetbooks
系统 MUST 为 sheetbook 资源提供可实现、可校验的 workflow YAML authoring surface:

- 资源声明:
  - `workflow.resources.sheetbooks.<sheetbook_id>.budget.max_sheets` MUST 为正整数
  - `workflow.resources.sheetbooks.<sheetbook_id>.budget.max_total_cells` MUST 为正整数
  - `workflow.resources.sheetbooks.<sheetbook_id>.export_xlsx.path` MAY 存在且 MUST 为非空字符串
  - `workflow.resources.sheetbooks.<sheetbook_id>.export_xlsx.write_lock` MAY 存在且 MUST 为 bool
- 写入简写（每个 demand run 可声明 0..N 条 write intents）:
  - `workflow.runs[*].writes` MAY 存在且 MUST 为数组
  - `workflow.runs[*].writes[*]` MUST 恰好包含一个 intent key
  - 对 sheetbook 相关 intent:
    - `workflow.runs[*].writes[*].sheetbook_sheet` MAY 存在（写入/覆盖 sheet）
    - `workflow.runs[*].writes[*].sheetbook_append` MAY 存在（追加写入 sheet）
- `writes[*].sheetbook_sheet` 对象字段 MUST 满足:
  - `sheetbook`: sheetbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `on_conflict` MAY 存在且 MUST 为 `error|overwrite|skip` 之一（默认 `error`）
- `writes[*].sheetbook_append` 对象字段 MUST 满足:
  - `sheetbook`: sheetbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `align_by` MAY 存在且 MUST 为 `field_id|header` 之一（默认 `field_id`）
  - `header_policy` MAY 存在且 MUST 为 `once|always|never` 之一（默认 `once`）
  - `on_mismatch` MAY 存在且 MUST 为 `error|warn|skip` 之一（默认 `error`）

#### Scenario: sheetbook authoring surface passes schema validation
- **WHEN** workflow YAML 包含 `workflow.resources.sheetbooks` 与 `workflow.runs[*].writes[*].sheetbook_sheet`
- **THEN** schema-only 校验 MUST 通过

### Requirement: writes to a sheetbook MUST be deterministic and conflict-safe
系统 MUST 支持将多个上游节点的输出写入同一个 sheetbook,并保证写入行为确定性与冲突安全:

- 对同一个 sheetbook 的写入 MUST 互斥/串行化,不得依赖并发完成时序
- 写入顺序 MUST 由 workflow YAML 的声明顺序决定（以 runs 列表顺序为一级 SSOT,以 `writes` 列表顺序为二级 SSOT）
- 当发生 sheet 名冲突/写入重复/字段对齐冲突时,系统 MUST fail-fast 并提供可诊断摘要

#### Scenario: deterministic order does not depend on completion timing
- **GIVEN** 两个并发执行的上游节点都写入同一个 sheetbook 的不同 sheet,且每个节点声明多条 `writes`
- **WHEN** 多次执行同一个 workflow
- **THEN** 生成的 sheet 顺序与内容 MUST 可复现

