## MODIFIED Requirements

### Requirement: workflow YAML exposes a stable authoring surface for shared resources and write intents
系统 MUST 为共享输出容器提供可实现、可校验的 workflow YAML authoring surface:

- 资源声明:
  - `workflow.resources.workbooks.<workbook_id>.path` MUST 为非空字符串
  - `workflow.resources.csvs.<csv_id>.path` MUST 为非空字符串
- 写入简写（每个 demand run 可声明 0..N 条 write intents）:
  - `workflow.runs[*].writes` MAY 存在且 MUST 为数组；缺省/空数组表示无写入意图
  - `workflow.runs[*].writes[*]` MUST 恰好包含一个 intent key（否则 fail-fast）
  - 每个 intent key MUST 为以下五者之一:
    - `workbook_sheet`
    - `workbook_append`
    - `csv_append`
    - `sheetbook_sheet`（由 `workflow-sheetbook-resources` 定义）
    - `sheetbook_append`（由 `workflow-sheetbook-resources` 定义）
- `writes[*].workbook_sheet` 对象字段 MUST 满足:
  - `workbook`: workbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `on_conflict` MAY 存在且 MUST 为 `error|overwrite|skip` 之一（默认 `error`）
- `writes[*].workbook_append` 对象字段 MUST 满足:
  - `workbook`: workbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `align_by` MAY 存在且 MUST 为 `field_id|header` 之一（默认 `field_id`）
  - `header_policy` MAY 存在且 MUST 为 `once|always|never` 之一（默认 `once`）
  - `on_mismatch` MAY 存在且 MUST 为 `error|warn|skip` 之一（默认 `error`）
- `writes[*].csv_append` 对象字段 MUST 满足:
  - `csv`: csv resource id
  - `output`: 上游 demand 的 output id
  - `header_policy` MAY 存在且 MUST 为 `once|always|never` 之一（默认 `once`）
  - `on_mismatch` MAY 存在且 MUST 为 `error|warn|skip` 之一（默认 `error`）

#### Scenario: shared-output authoring surface passes schema validation
- **WHEN** workflow YAML 同时包含 `workflow.resources` 与 `workflow.runs[*].writes`
- **THEN** schema-only 校验 MUST 通过

### Requirement: writes to shared resources are deterministic and serialized
系统 MUST 定义确定性写入顺序,且 MUST NOT 依赖并发完成顺序:
- 对同一共享资源的写入 MUST 互斥/串行化
- 写入顺序 MUST 由 workflow YAML 中 write intents 的声明顺序决定（以 runs 列表顺序为一级 SSOT,以 `writes` 列表顺序为二级 SSOT）,不得依赖线程调度或完成时序

#### Scenario: writes to a shared workbook are deterministic
- **GIVEN** 两个 runs 各自声明多条 `writes`,并写入同一个共享 workbook 的不同 sheet
- **WHEN** workflow 在并发模式下执行多次
- **THEN** 对共享资源的写入顺序 MUST 可复现,且结果 MUST 等价

