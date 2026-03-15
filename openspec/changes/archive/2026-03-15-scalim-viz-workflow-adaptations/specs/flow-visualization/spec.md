## MODIFIED Requirements

### Requirement: node_ref 命名规范
系统 SHALL 为 VizEvent 的 `node_ref` 使用稳定且可读的命名规范,确保跨快照与事件流一致.

#### Scenario: node_ref id 规范
- **WHEN** 生成 VizEvent 的 node_ref
- **THEN** id MUST 遵循以下格式:
  - pipeline: `pipeline`
  - batch: `batch:{batch_num}`
  - loader: `loader:{loader_name}`
  - field: `field:{field_key}`
  - source: `source:{source_id}`
  - output_target: `output_target:{target_id}`

## ADDED Requirements

### Requirement: VizGraphSnapshot 输出目标节点
系统 MUST 在启用多输出组合(output composition)时,在 VizGraphSnapshot 的依赖图中表达每个输出目标,使 UI 能在依赖图与事件流之间建立稳定关联.

系统 MUST 为每个输出目标创建一个 node:
- node.id MUST 为 `output_target:{target_id}`
- node.type MUST 为 `output_target`
- node.data MUST 至少包含 `target_id` 与可读的 `label`

系统 MUST 为 direct/derived 输出目标创建从输入字段到输出目标的依赖边:
- edge.source MUST 为 `field:{field_key}`
- edge.target MUST 为 `output_target:{target_id}`
- edge.type MUST 为 `composed_from`

说明:
- direct 输出目标的输入字段集合为 `layout.field_ids` 与可选 `requires`
- derived 输出目标的输入字段集合为 `derived.required_fields()` 与可选 `requires`
- meta/audit sheet(若存在)对应的输出目标节点 MUST 仍被创建;其边可省略

#### Scenario: composed outputs 在依赖图中可见
- **GIVEN** 运行请求配置了 output composition 且包含至少一个输出目标
- **WHEN** 生成 VizGraphSnapshot
- **THEN** nodes MUST 包含 `output_target:{target_id}` 节点
- **AND** direct/derived 输出目标 MUST 具有至少一条 `composed_from` 边(当其输入字段存在于快照字段节点中时)

### Requirement: OutputTargetEndEvent 映射为 output_target_finished
系统 MUST 将执行层的 `OutputTargetEndEvent` 映射为 VizEventStream 中的编排级事件,用于表达每个输出目标的写出统计与失败状态.

系统 MUST 以如下约定输出该 VizEvent:
- `event_type` MUST 为 `output_target_finished`
- `node_ref.type` MUST 为 `output_target`
- `node_ref.id` MUST 为 `output_target:{target_id}`
- payload MUST 至少包含: `target_id`, `row_count`, `error_count`, `duration_ms`, `disabled`
- 当 `output_path`/`sheet_name` 存在时,payload MUST 包含同名字段
- 当 `error_type`/`error_message` 存在时,payload MUST 包含同名字段

#### Scenario: 输出目标结束事件进入事件流
- **WHEN** 输出组合层发出 `OutputTargetEndEvent(target_id="summary", row_count=10, error_count=0, duration=1.2, disabled=false)`
- **THEN** VizEventStream MUST 追加一条 `event_type="output_target_finished"` 的事件
- **AND** 该事件 `node_ref.id` MUST 为 `output_target:summary`
- **AND** payload MUST 包含 `row_count=10` 与 `duration_ms=1200`

### Requirement: 前端展示 run_name/env
PROJECT_NAME Viz 前端 MUST 在回放 UI 中展示 run 的语义标签.

优先级规则:
- 当 `viz_snapshot.json` 的 `meta.viz.run_name` 存在时,UI MUST 将其作为主展示标签
- 否则,UI MUST 使用 `run_id` 作为主展示标签
- 当 `meta.viz.env` 存在时,UI MUST 展示该环境标识

#### Scenario: run_name 作为主标签
- **GIVEN** `viz_snapshot.json.meta.viz.run_name="wf:run-003"` 且 `meta.viz.env="prod"`
- **WHEN** 用户在 UI 中加载并查看该运行
- **THEN** UI MUST 显示 `wf:run-003` 作为主标签
- **AND** UI MUST 显示 `prod` 环境标识

### Requirement: 前端展示 output_target_finished 摘要
PROJECT_NAME Viz 前端 MUST 能解释 `output_target_finished` 事件,并在 timeline/inspector 中展示输出目标级摘要,以便在 composed outputs 场景下快速定位写出结果.

UI MUST 至少展示:
- `target_id`
- `row_count`, `error_count`, `duration_ms`, `disabled`
- `output_path` 与 `sheet_name`(当存在时;`output_path` 展示全路径)
- `error_type` 与 `error_message`(当存在时)

#### Scenario: inspector 展示输出目标事件详情
- **GIVEN** 事件流包含 `output_target_finished` 且 payload 含 `output_path`/`sheet_name`
- **WHEN** 用户在 UI 中查看该事件或选中对应输出目标节点
- **THEN** inspector MUST 展示该输出目标的行数/耗时/错误/禁用状态
- **AND** inspector MUST 展示 `output_path` 全路径与 `sheet_name`
