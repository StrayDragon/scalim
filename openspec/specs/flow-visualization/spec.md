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
- **GIVEN** 已存在的 `.tmp/artifacts/scalim-viz/examples/**/viz_events.jsonl`
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
系统 SHALL 为 VizEvent 的 `node_ref` 使用稳定且可读的命名规范,确保跨快照与事件流一致。

#### Scenario: node_ref id 规范
- **WHEN** 生成 VizEvent 的 node_ref
- **THEN** id MUST 遵循以下格式:
  - pipeline: `pipeline`
  - batch: `batch:{batch_num}`
  - loader: `loader:{loader_name}`
  - field: `field:{field_key}`
  - source: `source:{source_id}`
  - output_target: `output_target:{target_id}`
  - workflow_node: `workflow_node:{workflow_node_id}`
  - workflow_resource: `workflow_resource:{resource_type}:{resource_id}`

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

### Requirement: viz snapshot JSON output MUST be atomic and remain parseable under concurrency

当系统将 `VizGraphSnapshot` 落盘为 `viz_snapshot.json` 时，系统 MUST 保证写入原子性，避免读者读到半写文件或损坏 JSON：

- 系统 MUST 以“写入临时文件 + 原子替换（temp+replace）”的方式生成 `viz_snapshot.json`
- 在写入完成之前，读者读取目标路径时 MUST 看到旧版本（若存在）而不是半写内容
- 即使存在并发/重入写同一路径，最终落盘的 `viz_snapshot.json` MUST 始终可被 JSON 解析（允许最后写入者覆盖）

#### Scenario: concurrent snapshot writers do not corrupt JSON
- **GIVEN** 两个并发执行单元（线程或进程）写入同一个 `viz_snapshot.json` 目标路径
- **WHEN** 两者几乎同时触发 snapshot 写入
- **THEN** 文件内容 MUST 始终为可解析的 JSON
- **AND** 读者在任意时刻读取该路径 MUST 看到“旧版本或新版本”，不得读到半写文件

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

### Requirement: workflow replay bundle MUST be a first-class UI entry
当前端加载到 workflow replay bundle 时，系统 MUST 将 workflow 视图作为默认入口，而不是直接落到某个 child demand replay。

workflow 入口 MUST 基于 workflow scope run(`scalim-viz/workflow/`)内的 `viz_snapshot.json` 与 `viz_events.jsonl` 渲染 workflow 级图与状态摘要。

#### Scenario: workflow bundle opens at workflow scope by default
- **GIVEN** 用户加载一个包含 `scalim-viz/workflow/` run 的目录
- **WHEN** 前端完成初始化
- **THEN** 初始画面 MUST 为 workflow 视图
- **AND** 用户 MUST 能看到 workflow demand 节点，而不是被直接带入某个 child run

### Requirement: frontend MUST support drill-down from workflow demand nodes to child demand replay
前端 MUST 支持从 workflow demand 节点 drill-down 到对应的 child replay，并提供可预测的返回路径。

drill-down 交互 MUST 满足：

- 点击 demand 节点后，前端 MUST 能通过 `node.data.demand_run_id` 打开对应 demand run
- 返回 workflow 视图时 MUST 保留原先的 workflow 上下文(至少包含: viewMode、playbackIndex、选中节点、stage filter、focus、viewport)
- 当 child replay 缺失时，前端 MUST 给出可读的降级说明

#### Scenario: returning from demand replay preserves workflow context
- **GIVEN** 用户在 workflow 视图中选中了节点 `orders`
- **WHEN** 用户 drill-down 到 `orders` 的 child replay 后再返回 workflow 视图
- **THEN** 前端 MUST 回到先前的 workflow 上下文，而不是重置到默认位置

### Requirement: workflow demand nodes MUST expose an obvious drill-down affordance
workflow scope 画布中的 demand 节点 MUST 能一眼看出其 scope/语义,并提供可发现的 drill-down 动作(例如在 inspector 中出现"进入 demand 视图")。

#### Scenario: users can discover demand drill-down without guesswork
- **GIVEN** 用户打开 workflow scope 画布并选中一个 workflow demand 节点
- **WHEN** 用户查看 inspector
- **THEN** inspector MUST 展示该节点的 workflow 上下文信息
- **AND** inspector MUST 提供进入对应 demand run 的动作入口

### Requirement: workflow-first navigation MUST remain intuitive and accessible
workflow-first 回放 MUST 使用清晰的层级导航，而不是让用户在多个平铺视图中猜测当前 scope。

前端 MUST 至少满足：

- 提供 breadcrumb 或等价层级导航
- 键盘可达，tab 顺序与视觉顺序一致
- 提供清晰的 focus states
- 支持 `prefers-reduced-motion`
- 关键 drill-down / back 操作 MUST NOT 依赖 hover

#### Scenario: keyboard users can move between workflow scope and demand scope
- **WHEN** 用户仅使用键盘操作 workflow bundle 回放
- **THEN** 用户 MUST 能进入 child replay 并返回 workflow 视图
- **AND** 所有关键控件都 MUST 可聚焦且具有可见 focus 状态

### Requirement: workflow bundle loading MUST be additive to existing single-run replay loading
workflow bundle 支持 MUST 为增量扩展，不得破坏现有单 run replay 入口。

#### Scenario: standalone demand replay still works without workflow files
- **GIVEN** 用户加载一个只包含 `viz_snapshot.json` / `viz_events.jsonl` 的旧目录
- **WHEN** 前端完成初始化
- **THEN** 前端 MUST 继续按现有单 run replay 逻辑工作

### Requirement: Viz JSONL output MUST remain valid under concurrency

当并发执行产生 VizEventStream 且事件发射可能来自多个线程时,系统 MUST 保证输出的 JSONL 文件在并发下仍然可解析:
- 每一行 MUST 为完整 JSON 对象
- 行与行之间 MUST 不交错、不出现半行

#### Scenario: concurrent emission does not corrupt JSONL
- **WHEN** workflow 并发执行并触发多条 viz 事件
- **THEN** 输出的 `viz_events.jsonl` MUST 可被逐行 JSON 解析

### Requirement: run_id MUST be collision-resistant

系统 MUST 使用高熵的 run_id 生成策略,避免并发启动（同毫秒）导致的 run_id 碰撞与输出目录争用.

#### Scenario: parallel runs get distinct run_id
- **WHEN** 系统在极短时间内并发启动多个 run
- **THEN** 每个 run 的 `run_id` MUST 不相同

## Notes
- 前端实现位于 `frontend/scalim-viz/`(Svelte + Tailwind + XYFlow).
- 示例数据默认生成到 `.tmp/artifacts/scalim-viz/examples/`(不提交).

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
