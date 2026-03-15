# flow-visualization Specification

**状态: ✅ 已实现** - VizGraphSnapshot + VizEventStream 可视化机制已实现

## Purpose
提供执行过程的可视化输出:VizGraphSnapshot 从 ExecutionPlan 生成 XYFlow 兼容的 nodes/edges 结构用于依赖图展示;VizEventStream 将 Hook 事件映射为可视化事件流支持离线回放.

## Context
**FR032: 可视化数据流转**

提供静态和动态图表,用于观察数据流转状态:静态图(VizGraphSnapshot)、动态追踪(VizEventStream).

## Related Code (as implemented)
- `src/IMPL_ROOT/planning/viz.py` (VizGraphSnapshot builder)
- `src/IMPL_ROOT/planning/plan.py` (`ExecutionPlan.to_viz_graph_snapshot()` façade)
- `src/IMPL_ROOT/ob/presets/viz.py` (`VizObserver` + JSONL emitters)
## Requirements
### Requirement: 执行追踪 JSON 导出
系统 SHALL 通过 ExecutionTraceHook 导出包含 pipeline 元信息、统计与批次步骤的 JSON.

#### Scenario: 导出追踪数据
- **WHEN** ExecutionTraceHook 记录了执行过程
- **THEN** export_to_json 应输出包含 pipeline、statistics 与 batches 的 JSON 字符串

### Requirement: VizGraphSnapshot 计划图快照
系统 SHALL 能够从 ExecutionPlan 生成用于可视化的 VizGraphSnapshot,并提供与 XYFlow 兼容的 nodes/edges 结构.
VizGraphSnapshot MUST 为节点与边提供稳定的 `id`,以便与运行态事件流进行关联.

#### Scenario: 导出计划图快照
- **WHEN** 提供有效的 ExecutionPlan 并请求导出 VizGraphSnapshot
- **THEN** 输出 MUST 包含 nodes/edges 与 meta(目标字段、统计信息、schema_version 等),且节点/边可映射到字段/数据源依赖

### Requirement: VizGraphSnapshot schema_version
系统 SHALL 在 VizGraphSnapshot.meta 中写入 `schema_version` 与 `created_at`.

#### Scenario: 快照元数据
- **WHEN** 生成 VizGraphSnapshot
- **THEN** meta MUST 包含 `schema_version`(当前为 `vizgraph/v1`)与 `created_at` 时间戳

### Requirement: 并行阶段可视化
系统 SHALL 在 ExecutionPlan 存在 stages 时导出阶段分组信息,以支持并行阶段的可视化表达.

#### Scenario: 导出并行阶段分组
- **WHEN** ExecutionPlan.stages 非空
- **THEN** VizGraphSnapshot MUST 包含每个 stage 的 `stage_id`、`level` 与 `field_keys`,并允许 UI 将同级 stage 表达为可并行区域

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

### Requirement: 默认关闭与显式启用
系统 SHALL 在未配置 Viz 可视化输出参数(output_dir/output_path/snapshot_path/use_default_output_dir)时保持关闭,不输出 VizEventStream.

#### Scenario: 未配置可视化输出
- **WHEN** 用户未配置 output_dir/output_path/snapshot_path/use_default_output_dir
- **THEN** 系统不得输出 VizEventStream

### Requirement: VizEventStream 动态事件流
系统 SHALL 将执行事件(ObserverManager 分发)映射为 VizEvent 流,并支持 JSONL 文件输出.
VizEvent MUST 至少包含 `schema_version`、`run_id`、`event_type`、`timestamp` 与 `node_ref`.

#### Scenario: 输出 JSONL 事件流
- **WHEN** 启用 Viz 可视化观测且设置 output_path 或 output_dir
- **THEN** 系统应以 JSONL 追加写入事件流,用于离线回放

### Requirement: VizEvent schema_version
系统 SHALL 在每条 VizEvent 中写入 `schema_version`,且 MUST 为 `vizevent/v1`;事件体的 key/结构保持固定,`event_type` 等语义字段允许演进,但需在文档中维护映射说明.

#### Scenario: 兼容现有示例回放
- **GIVEN** 已存在的 `artifacts/scalim-viz/examples/**/viz_events.jsonl`
- **WHEN** 新版本产出 VizEventStream
- **THEN** 输出事件的 key/结构应与示例口径兼容(同一层级结构与必需字段),UI 可继续回放

### Requirement: VizEvent 映射与字段约定
系统 SHALL 按以下映射将执行事件转换为 VizEvent 的 `event_type` 与 `node_ref`,且 summary/sample 负载至少包含指定字段.

#### Scenario: 事件映射输出
- **WHEN** 执行事件进入 VizEventStream
- **THEN** VizEvent MUST 使用上述映射与字段约定

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

### Requirement: 数据负载策略
系统 SHALL 提供 payload_policy(`none|summary|sample|full`)控制事件数据负载,默认 `summary`.

#### Scenario: 负载策略为 summary
- **WHEN** payload_policy=summary
- **THEN** 事件 payload 应输出统计或样本摘要而非完整数据

#### Scenario: 负载策略为 sample
- **WHEN** payload_policy=sample
- **THEN** 事件 payload 应包含有限样本并遵守 sample_size 限制

### Requirement: Trace 输出开关
系统 SHALL 通过 `trace_enabled: bool` 控制是否输出高频 trace 事件文件 `viz_trace.jsonl`.
`trace_enabled=false` 时仅输出编排级事件流 `viz_events.jsonl`;`trace_enabled=true` 时额外输出 `viz_trace.jsonl`.
旧字段 `event_mode` 已移除;如仍配置该字段,系统 MUST 在配置校验阶段报错并提示迁移到 `trace_enabled`.

#### Scenario: trace_enabled=false
- **WHEN** trace_enabled=false
- **THEN** 系统 MUST NOT 输出 `viz_trace.jsonl`
- **THEN** `row_written` / `row_released` / `field_computed` / `relation_lookup` 等高频事件 MUST NOT 出现在 `viz_events.jsonl`

#### Scenario: trace_enabled=true
- **WHEN** trace_enabled=true
- **THEN** 系统 MUST 输出 `viz_trace.jsonl`
- **THEN** `viz_trace.jsonl` MUST 包含 `row_written` / `row_released` / `field_computed` / `relation_lookup` 等高频事件(当运行过程中触发时)

### Requirement: 快照元数据携带 Viz 配置
系统 SHALL 在 VizGraphSnapshot.meta.viz 中写入可视化相关配置,用于 UI 展示.

#### Scenario: 写入 meta.viz
- **WHEN** 生成 VizGraphSnapshot 且 VizObserverHook 已配置
- **THEN** meta.viz MUST 包含 `payload_policy`, `sample_size`, `trace_enabled`,并可选包含 `run_name` 与 `env`

### Requirement: 输出目录隔离
系统 SHALL 在仅配置 output_dir 时按 run 隔离输出,并自动追加 scalim-viz 目录.

#### Scenario: output_dir 自动追加 scalim-viz
- **WHEN** output_dir=/path/to/run-root 且 output_path/snapshot_path 未配置
- **THEN** 系统 MUST 写入 `/path/to/run-root/scalim-viz/<run_id>/viz_snapshot.json` 与 `/path/to/run-root/scalim-viz/<run_id>/viz_events.jsonl`
- **THEN** 当 trace_enabled=true 时系统 MUST 额外写入 `/path/to/run-root/scalim-viz/<run_id>/viz_trace.jsonl`

#### Scenario: output_dir 已包含 scalim-viz
- **WHEN** output_dir=/path/to/scalim-viz 且 output_path/snapshot_path 未配置
- **THEN** 系统 MUST 写入 `/path/to/scalim-viz/<run_id>/viz_snapshot.json` 与 `/path/to/scalim-viz/<run_id>/viz_events.jsonl`
- **THEN** 当 trace_enabled=true 时系统 MUST 额外写入 `/path/to/scalim-viz/<run_id>/viz_trace.jsonl`

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

### Requirement: PROJECT_NAME Viz 前端分层结构
PROJECT_NAME Viz 前端 MUST 将领域逻辑(domain)、副作用服务(services)与 UI 组件(ui)拆分为独立模块.
Domain 模块 MUST 为纯逻辑(无 DOM/FileSystem API 访问),services 模块 MUST 封装文件读取等副作用.

#### Scenario: UI 渲染依赖图
- **WHEN** 画布渲染节点与边
- **THEN** UI MUST 从 domain/state 读取渲染数据,且 MUST NOT 直接读取文件或解析 JSONL

### Requirement: 集中状态与动作入口
PROJECT_NAME Viz 前端 MUST 提供单一的 state/actions 入口管理图状态、回放状态与运行态数据,避免在多个面板组件中维护重复状态源.

#### Scenario: 回放进度更新
- **WHEN** 用户触发回放进度变更
- **THEN** 仅 state/actions 入口更新播放索引并派生新的视图状态,各面板通过选择器读取结果

### Requirement: App 壳薄化与面板隔离
顶层 App 壳 MUST 仅负责 provider 与布局组合,实际行为由独立面板组件负责.

#### Scenario: 查看节点详情
- **WHEN** 用户选中节点
- **THEN** 检查器面板从共享状态读取详情,且 MUST NOT 直接修改运行态 IO/轮询控制

## Notes
- 前端实现位于 `frontend/scalim-viz/`(Svelte + Tailwind + XYFlow).
- 示例数据位于 `artifacts/scalim-viz/examples/`.

### Requirement: VizObserver 热点必须分离配置、事件建模、快照增强与文件输出职责
系统 MUST 允许将 `ob/presets/viz.py` 按职责拆分为内部协作单元,至少包括配置/路径解析、执行事件到 VizEvent 的映射、快照与 meta 增强、文件输出/落盘.

#### Scenario: viz 热点拆分后职责边界清晰
- **WHEN** 维护者重构 `VizObserver` 相关实现
- **THEN** 配置解析、事件建模、快照增强与文件输出职责 MUST 可区分并独立审阅
- **AND** 不得继续要求这些职责长期聚合于单一热点模块

### Requirement: viz 热点拆分后输出契约保持稳定
系统 MUST 在 `ob/presets/viz.py` 内部拆分后继续保持 `viz_snapshot.json`、`viz_events.jsonl`、`viz_trace.jsonl` 的文件结构与既有产出契约稳定.

#### Scenario: viz 结构重构后产出契约保持一致
- **WHEN** 完成 `VizObserver` 内部职责拆分并生成可视化产物
- **THEN** 输出文件结构、关键字段与既有回放契约 MUST 与重构前保持兼容
