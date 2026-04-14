# performance-observability (delta) Specification

## ADDED Requirements

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
