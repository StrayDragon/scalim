---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate performance-observability --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "performance-observability"
purpose: "PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断."
requirements[6]{req_id,title,statement}:
  r1,性能指标采集与结构化输出,"系统 SHALL 提供可观测插件以收集总耗时/批次耗时/吞吐量/loader 统计与可选资源采样(psutil 可选). 系统 SHALL 提供结构化的 `PerformanceMetrics`(或等价结构),至少包含 `total_duration`、`batch_count`、`total_rows`、`batch_durations`、`stage_metrics`、`loader_stats` 与可选 `memory_samples`/`cpu_samples`. 系统 MUST 明确 `PerformanceMetrics.total_rows` 的统计口径为输入 `row_ids` 数量(例如 `sum(len(BatchStartEvent.row_ids))`),用于吞吐估算并避免 per-row 写出事件带来的额外开销. 系统 SHOULD 在文档/类型注释中提示: 若需要\"实际写出/产出(emit)行数\",应以 `ExecutionResult.total_rows` 为准. 系统 SHALL 通过更明确的阶段边界(例如 batch 内 loader/compute/write 的 begin/end)计算 `stage_metrics`,以减少基于事件间隔估算的误差."
  r2,duration 统计使用单调时钟,"系统 MUST 使用单调时钟(例如 `time.perf_counter()`)计算耗时指标(total/batch/stage/loader durations 或等价字段),以避免 `time.time()` 受系统时间回拨/校正影响导致的异常波动. 对于 observability presets/observers 中展示或派生 duration 的逻辑(例如 pretty logging 的批次耗时展示),实现 MUST 复用事件自带的 duration 字段(例如 `BatchEndEvent.duration`)或使用单调时钟计算;实现 MUST NOT 通过 `time.time()` 差值计算 duration."
  r3,资源采样与报告输出,"系统 SHALL 在启用 memory/cpu 指标时尝试使用 psutil 采样;sampling_interval 为批次数间隔(默认 1),memory_increase 由 pipeline start/end 的内存差计算. 系统 SHALL 支持 `console`/`json`/`csv`/`none` 四种报告格式;`json` 在 output_path 缺省时直接输出到 logger,`csv` 必须提供 output_path 否则记录警告. 系统 SHALL 支持阈值告警(如 `thresholds.batch_duration_warn` 与 `thresholds.memory_increase_warn`)并在超过阈值时记录警告日志."
  r4,runtime entrypoints 装配与独立开关,"系统 SHALL 支持通过 runtime entrypoints 装配 `PerformanceObserver` 与 `RelationObserver`(Observer presets),并允许两者独立启用/禁用: - 运行入口通过 `components=[...]` 接受 observers - YAML DSL MUST NOT 将 `observability.*` 作为稳定 authoring surface(legacy key 可 warning + ignore 作为迁移过渡)"
  r5,RelationObserver 统计与报告,"系统 SHALL 提供关联观测插件,收集 total/hit/miss/null_key/type_error 计数、per_source_stats,并支持 `sampling_rate` 与 `log_type_mismatch` 控制样本记录. 系统 SHALL 支持 `console`/`json`/`none` 报告格式."
  r6,adaptive 调度决策可观测性,"系统 SHALL 在 `parallel_mode=adaptive` 下提供可观测性信号用于解释调度决策(例如:命中阈值而退化串行、pool 限流导致排队、backend 选择与回退原因). 该可观测性信号 MUST 满足: - wants-gated:遵循 wants-gated/payload lazy 语义,未订阅时不得产生额外开销; - 可结构化:能够被 `PerformanceObserver`(或等价观测插件)收集并输出到报告结构中. 当前实现中,调度决策指标开关通过程序化配置(例如构造 `PerformanceObserver(..., include_scheduler_decisions=True)`)启用;YAML DSL 暂未暴露该显式开关."
scenarios[17]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,基础耗时监控,"","用户启用性能观测插件并配置 metrics={\"duration\"}",pipeline 结束时应可获取耗时与 loader 统计数据
  r1,阶段耗时可重复,"",在相同输入与相同执行计划下重复运行,`stage_metrics` 的统计口径应保持稳定且可解释(loader/compute/write 明确对应执行阶段)
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,"duration-非负且稳定","",执行一次 pipeline 并产出 performance metrics(或等价结构),`total_duration` 与所有 batch/stage/loader durations MUST 为非负数
  r2,"pretty-logging-uses-event-duration","",`PrettyLoggingObserver` 处理一个 `BatchEndEvent(duration=1.23)`,输出中展示的批次耗时 MUST 反映该事件的 `duration` 值(按渲染格式四舍五入)
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"内存监控-无-psutil","",用户配置 metrics 包含 memory/cpu 且环境未安装 psutil,系统应发出警告并禁用对应采样
  r3,"csv-输出缺少路径","",`report.format=csv` 且未提供 `report.output`,系统应记录警告而不中断执行
  r3,批次耗时超阈值,"","配置 `thresholds.batch_duration_warn: 10.0` 且某批次耗时超过 10 秒",系统应记录警告日志
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,仅启用关联可观测性,"",用户仅装配 `RelationObserver(...)` 且未装配 `PerformanceObserver(...)`,系统仅启用关联观测
  r5,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r5,关联命中率,"",pipeline 执行完成,`hit_rate` 应等于 `hit_count / (hit_count + miss_count)`
  r6,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r6,未启用观测时无额外开销,"",用户未启用性能观测且未订阅调度决策相关事件,`adaptive` 调度 MUST 不产生额外的事件构造与记录开销
  r6,程序化启用后可解释调度决策,"",用户通过代码启用性能观测并显式请求包含调度决策指标,报告中 MUST 包含串行退化原因、pool 等待统计或等价信息
```
