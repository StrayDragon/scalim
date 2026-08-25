# language: zh-CN
# capability: observability-flow-visualization
# purpose: 提供执行过程的可视化输出:VizGraphSnapshot 从 ExecutionPlan 生成 XYFlow 兼容的 nodes/edges 结构用于依赖图展示;VizEventStream 将 Hook 事件映射为可视化事件流支持离线回放. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: observability-flow-visualization

  @req:r61 @human
  场景: VizGraphSnapshot 生成与结构
    - 系统 SHALL 能够从 ExecutionPlan 生成用于可视化的 VizGraphSnapshot,并提供与 XYFlow 兼容的 nodes/edges 结构. VizGraphSnapshot MUST 为节点与边提供稳定的 `id`,以便与运行态事件流进行关联. 系统 SHALL 支持以下可视化结构: - **基本结构**: nodes/edges 与 meta(目标字段、统计信息、schema_version 等),节点/边可映射到字段/数据源依赖 - **并行阶段**: 当 ExecutionPlan.stages 非空时,包含每个 stage 的 `stage_id`、`level` 与 `field_keys`,允许 UI 将同级 stage 表达为可并行区域 - **输出目标节点**: 当启用多输出组合(output composition)时,为每个输出目标创建 node(`output_target:{target_id}`)与依赖边(`composed_from`)

  @req:r305 @human
  场景: schema_version 约定
    - 系统 SHALL 在所有可视化产物中写入 `schema_version` 以标识格式版本： - VizGraphSnapshot.meta MUST 包含 `schema_version`(当前为 `vizgraph/v1`)与 `created_at` - VizEvent MUST 包含 `schema_version`(当前为 `vizevent/v1`)，事件体的 key/结构保持固定

  @req:r428 @human
  场景: VizEventStream 事件流与映射
    - 系统 SHALL 在未配置 Viz 可视化输出参数时保持关闭,不输出 VizEventStream. 系统 SHALL 将执行事件(ObserverManager 分发)映射为 VizEvent 流,并支持 JSONL 文件输出: - VizEvent MUST 至少包含 `schema_version`、`run_id`、`event_type`、`timestamp` 与 `node_ref` - 系统 SHALL 按约定将执行事件转换为 VizEvent 的 `event_type` 与 `node_ref`,且 summary/sample 负载至少包含指定字段 - 系统 MUST 将执行层的 `OutputTargetEndEvent` 映射为 `output_target_finished` 事件,用于表达每个输出目标的写出统计与失败状态

  @req:r522 @human
  场景: node_ref 命名规范
    - 系统 SHALL 为 VizEvent 的 `node_ref` 使用稳定且可读的命名规范,确保跨快照与事件流一致。

  @req:r597 @human
  场景: 数据负载策略
    - 系统 SHALL 提供 payload_policy(`none|summary|sample|full`)控制事件数据负载,默认 `summary`.

  @req:r651 @human
  场景: Trace 输出开关
    - 系统 SHALL 通过 `trace_enabled: bool` 控制是否输出高频 trace 事件文件 `viz_trace.jsonl`. `trace_enabled=false` 时仅输出编排级事件流 `viz_events.jsonl`;`trace_enabled=true` 时额外输出 `viz_trace.jsonl`. 旧字段 `event_mode` 已移除;如仍配置该字段,系统 MUST 在配置校验阶段报错并提示迁移到 `trace_enabled`.

  @req:r695 @human
  场景: 快照元数据携带 Viz 配置
    - 系统 SHALL 在 VizGraphSnapshot.meta.viz 中写入可视化相关配置,用于 UI 展示.

  @req:r733 @human
  场景: 输出目录隔离
    - 系统 SHALL 在仅配置 output_dir 时按 run 隔离输出,并自动追加 scalim-viz 目录.

  @req:r765 @human
  场景: 并发输出安全性
    - 系统 MUST 保证可视化产物在并发场景下的完整性与原子性: **Snapshot 输出**: - 系统 MUST 以”写入临时文件 + 原子替换(temp+replace)”的方式生成 `viz_snapshot.json` - 在写入完成之前,读者读取目标路径时 MUST 看到旧版本(若存在)而不是半写内容 - 即使存在并发/重入写同一路径,最终落盘的 `viz_snapshot.json` MUST 始终可被 JSON 解析 **JSONL 输出**: - 每一行 MUST 为完整的 JSON 对象(以 `\n` 分隔) - 系统 MUST 避免并发写入导致的”半行”或”交错拼接”JSON - 系统 MUST 通过 single writer 或等价的写出串行化边界保证上述完整性

  @req:r146 @human
  场景: 前端架构与展示
    - PROJECT_NAME Viz 前端 MUST 满足以下架构与展示要求: **架构分层**: - 将领域逻辑、副作用服务与 UI 组件拆分为独立模块 - Domain 模块 MUST 为纯逻辑(无 DOM/FileSystem API 访问),services 模块 MUST 封装文件读取等副作用 - 提供单一的 state/actions 入口管理图状态、回放状态与运行态数据 - 顶层 App 壳 MUST 仅负责 provider 与布局组合,实际行为由独立面板组件负责 **展示要求**: - 在回放 UI 中展示 run 的语义标签(优先使用 `run_name`,否则使用 `run_id`,并展示 `env`) - 能解释 `output_target_finished` 事件,并在 timeline/inspector 中展示输出目标级摘要(包含 `target_id`, `row_count`, `error_count`, `duration_ms`, `disabled`, `output_path`, `sheet_name`, `error_type`, `error_message` 等)

  @req:r168 @human
  场景: Workflow 回放支持
    - 前端 MUST 支持 workflow replay bundle 作为一等入口,并提供直观的层级导航与 drill-down 交互: **Workflow 入口**: - 当加载 workflow replay bundle 时,将 workflow 视图作为默认入口(而非 child demand replay) - workflow 入口 MUST 基于 workflow scope run 内的 `viz_snapshot.json` 与 `viz_events.jsonl` 渲染 workflow 级图与状态摘要 - 支持 MUST 为增量扩展,不得破坏现有单 run replay 入口 **Drill-down 交互**: - 支持从 workflow demand 节点 drill-down 到对应的 child replay,并提供可预测的返回路径 - 点击 demand 节点后,前端 MUST 能通过 `node.data.demand_run_id` 打开对应 demand run - 返回 workflow 视图时 MUST 保留原先的 workflow 上下文(至少包含: viewMode、playbackIndex、选中节点、stage filter、focus、viewport) - 当 child replay 缺失时,前端 MUST 给出可读的降级说明 - workflow demand 节点 MUST 能一眼看出其 scope/语义,并提供可发现的 drill-down 动作 **导航可访问性**: - 提供 breadcrumb 或等价层级导航 - 键盘可达,tab 顺序与视觉顺序一致 - 提供清晰的 focus states - 支持 `prefers-reduced-motion` - 关键 drill-down / back 操作 MUST NOT 依赖 hover

  @req:r187 @human
  场景: run_id MUST be collision-resistant
    - 系统 MUST 使用高熵的 run_id 生成策略,避免并发启动（同毫秒）导致的 run_id 碰撞与输出目录争用.

  @req:r205 @human
  场景: VizObserver 职责分离与契约稳定
    - 系统 MUST 允许将 VizObserver 按职责拆分为内部协作单元,至少包括配置/路径解析、执行事件到 VizEvent 的映射、快照与 meta 增强、文件输出/落盘. 系统 MUST 在内部拆分后继续保持 `viz_snapshot.json`、`viz_events.jsonl`、`viz_trace.jsonl` 的文件结构与既有产出契约稳定.

  @req:r1000 @human
  场景: run_stats sibling 旁路
    - 系统 MAY 在 viz run 目录旁路写入 `run_stats.json`(见 `observability-run-stats`). 系统 MUST NOT 将完整 run_stats 载荷嵌入 `viz_snapshot.json`. 系统 MAY 在 `meta.viz` 中仅写入相对路径引用(例如 `run_stats`). 既有 snapshot/events/trace 文件名与加载契约 MUST 保持稳定.
  @req:r61 @human
  场景: 导出计划图快照
    - 必须成立：当 提供有效的 ExecutionPlan 并请求导出 VizGraphSnapshot；那么 输出 MUST 包含 nodes/edges 与 meta,且节点/边可映射到字段/数据源依赖
    当 提供有效的 ExecutionPlan 并请求导出 VizGraphSnapshot
    那么 输出 MUST 包含 nodes/edges 与 meta,且节点/边可映射到字段/数据源依赖

  @req:r61 @human
  场景: 导出并行阶段分组
    - 必须成立：当 ExecutionPlan.stages 非空；那么 VizGraphSnapshot MUST 包含每个 stage 的阶段信息,并允许 UI 将同级 stage 表达为可并行区域
    当 ExecutionPlan.stages 非空
    那么 VizGraphSnapshot MUST 包含每个 stage 的阶段信息,并允许 UI 将同级 stage 表达为可并行区域

  @req:r61 @human
  场景: composed-outputs-在依赖图中可见
    - 必须成立：假如 运行请求配置了 output composition 且包含至少一个输出目标；当 生成 VizGraphSnapshot；那么 nodes MUST 包含输出目标节点
    假如 运行请求配置了 output composition 且包含至少一个输出目标
    当 生成 VizGraphSnapshot
    那么 nodes MUST 包含输出目标节点
  @req:r305 @human
  场景: 快照与事件的-schema-version
    - 必须成立：当 生成 VizGraphSnapshot 或 VizEvent；那么 产物 MUST 包含对应的 `schema_version`
    当 生成 VizGraphSnapshot 或 VizEvent
    那么 产物 MUST 包含对应的 `schema_version`
  @req:r428 @human
  场景: 未配置可视化输出
    - 必须成立：当 用户未配置 output_dir/output_path/snapshot_path/use_default_output_dir；那么 系统不得输出 VizEventStream
    当 用户未配置 output_dir/output_path/snapshot_path/use_default_output_dir
    那么 系统不得输出 VizEventStream

  @req:r428 @human
  场景: 输出-jsonl-事件流
    - 必须成立：当 启用 Viz 可视化观测且设置 output_path 或 output_dir；那么 系统应以 JSONL 追加写入事件流,用于离线回放
    当 启用 Viz 可视化观测且设置 output_path 或 output_dir
    那么 系统应以 JSONL 追加写入事件流,用于离线回放

  @req:r428 @human
  场景: 事件映射输出
    - 必须成立：当 执行事件进入 VizEventStream；那么 VizEvent MUST 使用约定的映射与字段约定
    当 执行事件进入 VizEventStream
    那么 VizEvent MUST 使用约定的映射与字段约定

  @req:r428 @human
  场景: 输出目标结束事件进入事件流
    - 必须成立：当 输出组合层发出 `OutputTargetEndEvent`；那么 VizEventStream MUST 追加一条 `event_type="output_target_finished"` 的事件
    当 输出组合层发出 `OutputTargetEndEvent`
    那么 VizEventStream MUST 追加一条 `event_type="output_target_finished"` 的事件
  @req:r522 @human
  场景: node-ref-id-规范
    - 必须成立：当 生成 VizEvent 的 node_ref；那么 id MUST 遵循以下格式: pipeline: `pipeline` batch: `batch:{batch_num}` loader: `loader:{loader_name}` field: `field:{field_key}` source: `source:{source_id}` output_target: `output_target:{target_id}` workflow_node: `workflow_node:{workflow_node_id}` workflow_resource: `workflow_resource:{resource_type}:{resource_id}`
    当 生成 VizEvent 的 node_ref
    那么 id MUST 遵循以下格式: pipeline: `pipeline` batch: `batch:{batch_num}` loader: `loader:{loader_name}` field: `field:{field_key}` source: `source:{source_id}` output_target: `output_target:{target_id}` workflow_node: `workflow_node:{workflow_node_id}` workflow_resource: `workflow_resource:{resource_type}:{resource_id}`
  @req:r597 @human
  场景: 负载策略为-summary
    - 必须成立：当 payload_policy=summary；那么 事件 payload 应输出统计或样本摘要而非完整数据
    当 payload_policy=summary
    那么 事件 payload 应输出统计或样本摘要而非完整数据

  @req:r597 @human
  场景: 负载策略为-sample
    - 必须成立：当 payload_policy=sample；那么 事件 payload 应包含有限样本并遵守 sample_size 限制
    当 payload_policy=sample
    那么 事件 payload 应包含有限样本并遵守 sample_size 限制
  @req:r651 @human
  场景: trace-enabled-false
    - 必须成立：当 trace_enabled=false；那么 系统 MUST NOT 输出 `viz_trace.jsonl`
    当 trace_enabled=false
    那么 系统 MUST NOT 输出 `viz_trace.jsonl`

  @req:r651 @human
  场景: trace-enabled-true
    - 必须成立：当 trace_enabled=true；那么 系统 MUST 输出 `viz_trace.jsonl`
    当 trace_enabled=true
    那么 系统 MUST 输出 `viz_trace.jsonl`
  @req:r695 @human
  场景: 写入-meta-viz
    - 必须成立：当 生成 VizGraphSnapshot 且 VizObserverHook 已配置；那么 meta.viz MUST 包含 `payload_policy`, `sample_size`, `trace_enabled`,并可选包含 `run_name` 与 `env`
    当 生成 VizGraphSnapshot 且 VizObserverHook 已配置
    那么 meta.viz MUST 包含 `payload_policy`, `sample_size`, `trace_enabled`,并可选包含 `run_name` 与 `env`
  @req:r733 @human
  场景: output-dir-自动追加-scalim-viz
    - 必须成立：当 output_dir=/path/to/run-root 且 output_path/snapshot_path 未配置；那么 系统 MUST 写入 `/path/to/run-root/scalim-viz/<run_id>/viz_snapshot.json` 与 `/path/to/run-root/scalim-viz/<run_id>/viz_events.jsonl`
    当 output_dir=/path/to/run-root 且 output_path/snapshot_path 未配置
    那么 系统 MUST 写入 `/path/to/run-root/scalim-viz/<run_id>/viz_snapshot.json` 与 `/path/to/run-root/scalim-viz/<run_id>/viz_events.jsonl`

  @req:r733 @human
  场景: output-dir-已包含-scalim-viz
    - 必须成立：当 output_dir=/path/to/scalim-viz 且 output_path/snapshot_path 未配置；那么 系统 MUST 写入 `/path/to/scalim-viz/<run_id>/viz_snapshot.json` 与 `/path/to/scalim-viz/<run_id>/viz_events.jsonl`
    当 output_dir=/path/to/scalim-viz 且 output_path/snapshot_path 未配置
    那么 系统 MUST 写入 `/path/to/scalim-viz/<run_id>/viz_snapshot.json` 与 `/path/to/scalim-viz/<run_id>/viz_events.jsonl`
  @req:r765 @human
  场景: concurrent-snapshot-writers-do-not-corrupt-json
    - 必须成立：假如 两个并发执行单元写入同一个 `viz_snapshot.json` 目标路径；当 两者几乎同时触发 snapshot 写入；那么 文件内容 MUST 始终为可解析的 JSON
    假如 两个并发执行单元写入同一个 `viz_snapshot.json` 目标路径
    当 两者几乎同时触发 snapshot 写入
    那么 文件内容 MUST 始终为可解析的 JSON

  @req:r765 @human
  场景: concurrent-emit-does-not-corrupt-jsonl-lines
    - 必须成立：假如 workflow 并发执行且多个线程并发调用同一个 emitter 的 `emit()`；当 事件写入完成并读取输出的 JSONL 文件逐行解析；那么 每一行 MUST 为可解析的 JSON
    假如 workflow 并发执行且多个线程并发调用同一个 emitter 的 `emit()`
    当 事件写入完成并读取输出的 JSONL 文件逐行解析
    那么 每一行 MUST 为可解析的 JSON
  @req:r146 @human
  场景: ui-渲染依赖图
    - 必须成立：当 画布渲染节点与边；那么 UI MUST 从 domain/state 读取渲染数据,且 MUST NOT 直接读取文件或解析 JSONL
    当 画布渲染节点与边
    那么 UI MUST 从 domain/state 读取渲染数据,且 MUST NOT 直接读取文件或解析 JSONL

  @req:r146 @human
  场景: run-name-作为主标签
    - 必须成立：假如 `viz_snapshot.json.meta.viz.run_name="wf:run-003"` 且 `meta.viz.env="prod"`；当 用户在 UI 中加载并查看该运行；那么 UI MUST 显示 `wf:run-003` 作为主标签
    假如 `viz_snapshot.json.meta.viz.run_name="wf:run-003"` 且 `meta.viz.env="prod"`
    当 用户在 UI 中加载并查看该运行
    那么 UI MUST 显示 `wf:run-003` 作为主标签

  @req:r146 @human
  场景: inspector-展示输出目标事件详情
    - 必须成立：假如 事件流包含 `output_target_finished` 且 payload 含 `output_path`/`sheet_name`；当 用户在 UI 中查看该事件或选中对应输出目标节点；那么 inspector MUST 展示该输出目标的行数/耗时/错误/禁用状态
    假如 事件流包含 `output_target_finished` 且 payload 含 `output_path`/`sheet_name`
    当 用户在 UI 中查看该事件或选中对应输出目标节点
    那么 inspector MUST 展示该输出目标的行数/耗时/错误/禁用状态
  @req:r168 @human
  场景: workflow-bundle-opens-at-workflow-scope-by-default
    - 必须成立：假如 用户加载一个包含 workflow run 的目录；当 前端完成初始化；那么 初始画面 MUST 为 workflow 视图
    假如 用户加载一个包含 workflow run 的目录
    当 前端完成初始化
    那么 初始画面 MUST 为 workflow 视图

  @req:r168 @human
  场景: returning-from-demand-replay-preserves-workflow-context
    - 必须成立：假如 用户在 workflow 视图中选中了节点；当 用户 drill-down 到该节点的 child replay 后再返回 workflow 视图；那么 前端 MUST 回到先前的 workflow 上下文，而不是重置到默认位置
    假如 用户在 workflow 视图中选中了节点
    当 用户 drill-down 到该节点的 child replay 后再返回 workflow 视图
    那么 前端 MUST 回到先前的 workflow 上下文，而不是重置到默认位置

  @req:r168 @human
  场景: users-can-discover-demand-drill-down-without-guesswork
    - 必须成立：假如 用户打开 workflow scope 画布并选中一个 workflow demand 节点；当 用户查看 inspector；那么 inspector MUST 展示该节点的 workflow 上下文信息
    假如 用户打开 workflow scope 画布并选中一个 workflow demand 节点
    当 用户查看 inspector
    那么 inspector MUST 展示该节点的 workflow 上下文信息

  @req:r168 @human
  场景: keyboard-users-can-move-between-workflow-scope-and-demand-sc
    - 必须成立：当 用户仅使用键盘操作 workflow bundle 回放；那么 用户 MUST 能进入 child replay 并返回 workflow 视图
    当 用户仅使用键盘操作 workflow bundle 回放
    那么 用户 MUST 能进入 child replay 并返回 workflow 视图

  @req:r168 @human
  场景: standalone-demand-replay-still-works-without-workflow-files
    - 必须成立：假如 用户加载一个只包含 `viz_snapshot.json` / `viz_events.jsonl` 的旧目录；当 前端完成初始化；那么 前端 MUST 继续按现有单 run replay 逻辑工作
    假如 用户加载一个只包含 `viz_snapshot.json` / `viz_events.jsonl` 的旧目录
    当 前端完成初始化
    那么 前端 MUST 继续按现有单 run replay 逻辑工作
  @req:r187 @human
  场景: parallel-runs-get-distinct-run-id
    - 必须成立：当 系统在极短时间内并发启动多个 run；那么 每个 run 的 `run_id` MUST 不相同
    当 系统在极短时间内并发启动多个 run
    那么 每个 run 的 `run_id` MUST 不相同
  @req:r205 @human
  场景: viz-热点拆分后职责边界清晰
    - 必须成立：当 维护者重构 VizObserver 相关实现；那么 配置解析、事件建模、快照增强与文件输出职责 MUST 可区分并独立审阅
    当 维护者重构 VizObserver 相关实现
    那么 配置解析、事件建模、快照增强与文件输出职责 MUST 可区分并独立审阅

  @req:r205 @human
  场景: viz-结构重构后产出契约保持一致
    - 必须成立：当 完成 VizObserver 内部职责拆分并生成可视化产物；那么 输出文件结构、关键字段与既有回放契约 MUST 与重构前保持兼容
    当 完成 VizObserver 内部职责拆分并生成可视化产物
    那么 输出文件结构、关键字段与既有回放契约 MUST 与重构前保持兼容

  @req:r1000 @human
  场景: run-stats-sibling-not-embedded
    - 必须成立：当 write viz snapshot and optional run_stats；那么 snapshot MUST NOT embed full run_stats object
    当 write viz snapshot and optional run_stats
    那么 snapshot MUST NOT embed full run_stats object
