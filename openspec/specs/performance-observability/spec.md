# performance-observability Specification

**状态: ✅ 已实现**
## Purpose
PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断.

## Context
PROJECT_DIST_NAME 框架需要完备的性能监控能力来帮助用户:
- 了解执行耗时分布
- 监控资源使用(内存、CPU)
- 识别性能瓶颈
- 生成报告用于分析和优化

当前实现通过 `PerformanceObserver` 与 `RelationObserver`(Observer presets)提供可观测性入口;核心指标结构定义在 `src/IMPL_ROOT/ob/perf_metrics.py`,实现位于 `src/IMPL_ROOT/ob/presets/performance.py` 与 `src/IMPL_ROOT/ob/presets/relations.py`.
## Related Code (as implemented)
- `src/IMPL_ROOT/ob/presets/performance.py` (`PerformanceObserver`)
- `src/IMPL_ROOT/ob/presets/relations.py` (`RelationObserver`)
- `src/IMPL_ROOT/ob/perf_metrics.py` (structured metrics models)
- `src/IMPL_ROOT/ob/presets/logs.py` (`PrettyLoggingObserver`)
- `src/IMPL_ROOT/ob/manager.py` (wants-gated dispatch)
## Requirements
### Requirement: 性能指标采集与结构化输出
系统 SHALL 提供可观测插件以收集总耗时/批次耗时/吞吐量/loader 统计与可选资源采样(psutil 可选).
系统 SHALL 提供结构化的 `PerformanceMetrics`(或等价结构),至少包含 `total_duration`、`batch_count`、`total_rows`、`batch_durations`、`stage_metrics`、`loader_stats` 与可选 `memory_samples`/`cpu_samples`.
系统 MUST 明确 `PerformanceMetrics.total_rows` 的统计口径为输入 `row_ids` 数量(例如 `sum(len(BatchStartEvent.row_ids))`),用于吞吐估算并避免 per-row 写出事件带来的额外开销.
系统 SHOULD 在文档/类型注释中提示: 若需要"实际写出/产出(emit)行数",应以 `ExecutionResult.total_rows` 为准.
系统 SHALL 通过更明确的阶段边界(例如 batch 内 loader/compute/write 的 begin/end)计算 `stage_metrics`,以减少基于事件间隔估算的误差.

#### Scenario: 基础耗时监控
- **WHEN** 用户启用性能观测插件并配置 metrics={"duration"}
- **THEN** pipeline 结束时应可获取耗时与 loader 统计数据

#### Scenario: 阶段耗时可重复
- **WHEN** 在相同输入与相同执行计划下重复运行
- **THEN** `stage_metrics` 的统计口径应保持稳定且可解释(loader/compute/write 明确对应执行阶段)

### Requirement: duration 统计使用单调时钟
系统 MUST 使用单调时钟(例如 `time.perf_counter()`)计算耗时指标(total/batch/stage/loader durations 或等价字段),以避免 `time.time()` 受系统时间回拨/校正影响导致的异常波动.

对于 observability presets/observers 中展示或派生 duration 的逻辑(例如 pretty logging 的批次耗时展示),实现 MUST 复用事件自带的 duration 字段(例如 `BatchEndEvent.duration`)或使用单调时钟计算;实现 MUST NOT 通过 `time.time()` 差值计算 duration.

#### Scenario: duration 非负且稳定
- **WHEN** 执行一次 pipeline 并产出 performance metrics(或等价结构)
- **THEN** `total_duration` 与所有 batch/stage/loader durations MUST 为非负数

#### Scenario: pretty logging uses event duration
- **WHEN** `PrettyLoggingObserver` 处理一个 `BatchEndEvent(duration=1.23)`
- **THEN** 输出中展示的批次耗时 MUST 反映该事件的 `duration` 值(按渲染格式四舍五入)

### Requirement: 资源采样与报告输出
系统 SHALL 在启用 memory/cpu 指标时尝试使用 psutil 采样;sampling_interval 为批次数间隔(默认 1),memory_increase 由 pipeline start/end 的内存差计算.
系统 SHALL 支持 `console`/`json`/`csv`/`none` 四种报告格式;`json` 在 output_path 缺省时直接输出到 logger,`csv` 必须提供 output_path 否则记录警告.
系统 SHALL 支持阈值告警(如 `thresholds.batch_duration_warn` 与 `thresholds.memory_increase_warn`)并在超过阈值时记录警告日志.

#### Scenario: 内存监控(无 psutil)
- **WHEN** 用户配置 metrics 包含 memory/cpu 且环境未安装 psutil
- **THEN** 系统应发出警告并禁用对应采样

#### Scenario: CSV 输出缺少路径
- **WHEN** `report.format=csv` 且未提供 `report.output`
- **THEN** 系统应记录警告而不中断执行

#### Scenario: 批次耗时超阈值
- **WHEN** 配置 `thresholds.batch_duration_warn: 10.0` 且某批次耗时超过 10 秒
- **THEN** 系统应记录警告日志

### Requirement: runtime entrypoints 装配与独立开关
系统 SHALL 支持通过 runtime entrypoints 装配 `PerformanceObserver` 与 `RelationObserver`(Observer presets),并允许两者独立启用/禁用:

- 运行入口通过 `components=[...]` 接受 observers
- YAML DSL MUST NOT 将 `observability.*` 作为稳定 authoring surface(legacy key 可 warning + ignore 作为迁移过渡)

#### Scenario: 仅启用关联可观测性
- **WHEN** 用户仅装配 `RelationObserver(...)` 且未装配 `PerformanceObserver(...)`
- **THEN** 系统仅启用关联观测

### Requirement: RelationObserver 统计与报告
系统 SHALL 提供关联观测插件,收集 total/hit/miss/null_key/type_error 计数、per_source_stats,并支持 `sampling_rate` 与 `log_type_mismatch` 控制样本记录.
系统 SHALL 支持 `console`/`json`/`none` 报告格式.

#### Scenario: 关联命中率
- **WHEN** pipeline 执行完成
- **THEN** `hit_rate` 应等于 `hit_count / (hit_count + miss_count)`

### Requirement: adaptive 调度决策可观测性
系统 SHALL 在 `parallel_mode=adaptive` 下提供可观测性信号用于解释调度决策(例如:命中阈值而退化串行、pool 限流导致排队、backend 选择与回退原因).

该可观测性信号 MUST 满足:
- wants-gated:遵循 `hooks-observability-structure` 的 wants-gated/payload lazy 语义,未订阅时不得产生额外开销;
- 可结构化:能够被 `PerformanceObserver`(或等价观测插件)收集并输出到报告结构中.
当前实现中,调度决策指标开关通过程序化配置(例如构造 `PerformanceObserver(..., include_scheduler_decisions=True)`)启用;YAML DSL 暂未暴露该显式开关.

#### Scenario: 未启用观测时无额外开销
- **WHEN** 用户未启用性能观测且未订阅调度决策相关事件
- **THEN** `adaptive` 调度 MUST 不产生额外的事件构造与记录开销

#### Scenario: 程序化启用后可解释调度决策
- **WHEN** 用户通过代码启用性能观测并显式请求包含调度决策指标
- **THEN** 报告中 MUST 包含串行退化原因、pool 等待统计或等价信息

### Requirement: console reports in observability presets MUST follow dependency-free-console-reports

系统 MUST 确保 observability presets（至少包括 `PerformancePresentationLayer` 与 `RelationObserver`）在 `report_format=console` 时的输出满足 `dependency-free-console-reports` 的约束：

- 稳定前缀 `[scalim] <subsystem>:`
- 稳定 kind token（例如 `summary`、`per_source`、`stage`、`loader`）
- 逐行 `k=v` 输出（key 顺序稳定，`None` 省略）
- 不依赖表格渲染器（不得使用 `scalim.vendor.literich`）

#### Scenario: relations console report is line oriented and grep-friendly
- **GIVEN** 用户启用 `RelationObserver` 且 `report_format=console`
- **WHEN** pipeline 结束触发报告输出
- **THEN** 输出 MUST 至少包含一行 kind=`summary` 且包含 `total_lookups=` 与 `hit_rate=` 字段
- **AND** 对每个 source 统计，输出 MUST 以 kind=`per_source` 的重复行表达

#### Scenario: performance console report contains summary and optional breakdown lines
- **GIVEN** 用户启用 `PerformanceObserver` 且 `report_format=console`
- **WHEN** pipeline 结束触发报告输出
- **THEN** 输出 MUST 至少包含一行 kind=`summary` 且包含 `total_duration_s=` 与 `batch_count=` 字段
- **AND** 当存在 stage/loader 统计时，输出 SHOULD 追加 kind=`stage`/`loader` 的逐行明细

### Requirement: changing console formatting MUST NOT change metrics semantics

系统 MUST 将本变更视为 “展示层变更”；任何 console 输出格式的调整 MUST NOT 改变既有 `PerformanceMetrics` / `RelationMetrics` 的统计口径与字段值域。

#### Scenario: JSON/CSV report semantics remain unchanged
- **GIVEN** 用户选择 `report_format=json` 或 `report_format=csv`
- **WHEN** 输出报告
- **THEN** 报告中的字段集合与语义 MUST 与变更前保持一致（仅 console 展示形态变化）

### Requirement: performance/relations report records MUST include demand attribution when available

系统 MUST 在 `scalim.performance` 与 `scalim.relations` 的结构化 report 记录（JSONL，每条记录一行）中携带可 join 的 demand 归因字段（当存在时）：

- `demand`: 用户声明的 demand 名称（例如 demand YAML 的 `demand.name`；来自 `DemandIr.name`）
- `workflow_node_id`: workflow 节点内部稳定 id（当处于 workflow 场景；等于 workflow YAML 的 `runs[*].id`）
- `demand_path`: demand YAML 路径（当处于 workflow 场景且可获取时）

系统可以追加其它归因字段（例如 `workflow_exec_id`、`workflow_node_decl_order`），但 MUST 至少覆盖上述三项（当存在时）。

#### Scenario: report records are grep-joinable by demand and node id
- **GIVEN** 某次 demand 执行的事件流携带 `Event.meta.demand=<name>` 且处于 workflow 场景并携带 `Event.meta.workflow_node_id=<id>`
- **WHEN** pipeline 结束触发 `PerformanceObserver` 与 `RelationObserver` 输出结构化 report 记录
- **THEN** 两个 subsystem 的每条 report 记录 MUST 包含 `demand=<name>` 与 `workflow_node_id=<id>`

### Requirement: main_source streaming wall time MUST be observable per batch and aggregated in performance report

系统 MUST 以“每批拉取 batch_rows 的 wall time”为口径统计 main_source streaming 时间，并将该时间在 performance report 中可见化：

- streaming 统计 MUST 为 wants-gated（未订阅相关事件时不得引入额外开销）
- streaming 统计 MUST 按 batch 归因（包含 `batch_num`）

#### Scenario: streaming time is emitted as a stage span
- **GIVEN** 至少存在一个订阅者使得 `InstrumentationHub.wants("stage_span")=true`
- **WHEN** pipeline 执行并逐批从 main_rows 中拉取 batch_rows
- **THEN** 系统 MUST 为每个 batch 发出一个 `stage_span` 事件，且 `stage="stream"` 并包含该 batch 的 streaming wall time

### Requirement: performance report MUST separate stream_s from source_lookup_s

系统 MUST 在 performance report 中提供可解释的 breakdown，使用户能够区分“主表 streaming”与“source lookup”：

- `stream_s`: main_source streaming wall time（按 `stage="stream"` 汇总）
- `source_lookup_s`: source lookup wall time（Load/LoadRef 阶段；按 `stage="loader"` 汇总）
- 系统 MUST 显式暴露 `untracked_overhead_s = total_duration - (stream_s + loader_s + compute_s + write_s)`（或等价字段），避免黑盒时间导致误判

#### Scenario: tuning direction can be decided from one report
- **WHEN** pipeline 结束触发 `PerformanceObserver` 输出结构化 report 记录
- **THEN** report MUST 至少包含一条表达 stream vs lookup 的 breakdown（一个 kind 记录即可）

### Requirement: per-loader timing stats MUST be available without enabling per-batch verbose lines

系统 MUST 提供独立开关，使用户可以在不输出 per-batch verbose 记录的前提下看到 per-loader（per-source）耗时统计：

- 该输出 MUST 至少包含每个 loader 的 `total_duration`（或 `total_s`）与 `exec_calls`（或等价字段）
- 系统 SHALL 支持按耗时排序输出 top-N，以便直接定位最慢 source

#### Scenario: loader top-N is emitted with low noise
- **GIVEN** 用户启用 per-loader stats 输出但未启用 per-batch verbose 输出
- **WHEN** pipeline 结束触发 performance 结构化 report
- **THEN** report MUST 输出 per-loader 耗时统计记录
- **AND** report MUST NOT 输出 per-batch verbose 记录

### Requirement: per-field compute profiling MUST be opt-in and operator-level (not per-row)

系统 SHALL 提供 per-field compute top-N profiling 能力，但 MUST 满足：

- opt-in：默认关闭
- wants-gated：未启用时不得构造与 operator 数量成正比的额外 span/事件
- operator-level：按 `ComputeOperator` 粒度统计（每 field 每 batch 最多一条 span），不得采用逐行 `field_compute` 事件作为实现基础

#### Scenario: compute profiling adds no overhead when disabled
- **GIVEN** 用户未启用 per-field compute profiling
- **WHEN** 执行一次包含大量行的 pipeline
- **THEN** 系统 MUST 不发出 operator-level compute span（或等价事件）

### Requirement: batch duration distribution MUST be included in performance report

系统 MUST 在 performance 结构化 report 中提供批次耗时分布统计，至少包含：

- `min_s`、`max_s`
- `p50_s`、`p90_s`
- `stddev_s`

#### Scenario: batch distribution is present
- **WHEN** pipeline 结束触发 performance 结构化 report
- **THEN** 输出 MUST 至少包含一条 batch duration distribution（一个 kind 记录即可）

### Requirement: system SHALL provide opt-in advisor hints based on runtime perf stats

系统 SHALL 提供一个 opt-in 的 advisor hints 输出通道，用于基于运行时统计给出可操作建议（示例）：

- low hit-rate source → consider preload_forever
- compute-bound → batch_size 调优收益有限
- streaming-dominated → 优先关注 DB/streaming 而不是 source lookup

#### Scenario: advisor emits hints only when enabled
- **GIVEN** 用户启用 advisor hints 输出
- **WHEN** pipeline 结束
- **THEN** 系统 MUST 输出 0..N 条 hint 记录（允许 0），且每条 hint MUST 携带 demand 归因字段

## Notes
- `stage_metrics` 来自 batch 内 loader/compute/write 事件区间 wall time,并按批次累计;总和不应超过 `total_duration`.
- `PerformanceObserver` 的阶段耗时为事件区间的近似值,不代表精确 CPU 时间.
