# language: zh-CN
# capability: observability-run-stats
# purpose: 低漂移自我观测底座：版本化 run_stats、workflow nodes[] 快照、bench/debug profiles、高影响观测警告，以及可选 viz sibling 产物。
# scope: src/scalim/

功能: observability-run-stats

  @req:r990 @human
  场景: run_stats 契约
    - 系统 SHALL 提供版本化结构化 run_stats(schema 标识如 `scalim_run_stats/v1`),至少包含 `pipeline`(含 duration/batches/rows/node_count)、`stages_total`、`loaders`、`outputs`、`memory`(可选)、`nodes[]`。运行时 SSOT MUST 为 dataclass(或等价);落盘默认 builtin JSON(stdlib);MUST NOT 引入新的必选 PyPI 依赖。

  @req:r991 @human
  场景: workflow 多 demand 快照
    - 当同一 observer/accumulator 实例跨多个 demand pipeline 复用时,系统 MUST 在每个 `PIPELINE_END` 保留该节点快照于 `nodes[]`(或等价结构)。系统 MUST NOT 仅暴露最后一次 pipeline 的内存态指标并宣称其为整个 workflow 的完整结论。

  @req:r992 @human
  场景: 事件平面约束
    - run_stats 采集 MUST 仅订阅已有 EventType(至少覆盖 PIPELINE_*/BATCH_*/STAGE_SPAN/LOADER_CALL,以及可选 OUTPUT_TARGET_END)。系统 MUST NOT 为 run_stats 另开与 wants-gated 冲突的热路径 instrumentation。

  @req:r993 @human
  场景: 观测 profiles
    - 系统 SHALL 提供可装配的观测 profile:`baseline`(无组件)、`bench`(lite 耗时/阶段/loader/outputs + 可选 memory)、`bench_plus`(疏采样 stage memory)、`debug`(可含 relation/operator_span/viz summary)。生产默认 MUST 仍可为 `components=[]`。

  @req:r994 @human
  场景: 高影响观测警告
    - 启用下列任一能力时系统 MUST 发出警告(UserWarning 或结构化日志),并指明开销类别与更低漂移替代(如 bench):`RELATION_LOOKUP` 诊断、`OPERATOR_SPAN`/field_compute top-N、`viz_trace` 或 `payload_policy=full`、在超大 batch 数下持久化全量 `batches[]`/batch lines。

  @req:r995 @human
  场景: psutil 内存策略
    - 当 profile/配置显式请求 memory(或 cpu)采样且环境无 psutil 时,bench 路径 MUST fail-fast(或明确拒绝该 profile),MUST NOT 静默假装已采集 peak RSS。与仅 duration 的 bench 可并存。

  @req:r996 @human
  场景: 输出等价
    - 启用 bench(或等价 lite)观测时,系统 MUST NOT 改变 sink 业务输出内容;测试 SHALL 能用 CSV 行数/内容哈希对拍 baseline。

  @req:r997 @human
  场景: viz sibling
    - 当启用 Viz 输出时,系统 MAY 在同一 run 目录旁路写入 `run_stats.json`。系统 MUST NOT 把完整 run_stats 载荷嵌入 `viz_snapshot.json` 图契约。系统 MAY 仅写入路径引用(例如 meta.viz.run_stats)。

  @req:r990 @human
  场景: schema-present
    - 必须成立：当 导出 run_stats 结构；那么 payload MUST 含 schema 标识与 pipeline/stages_total/loaders/nodes 键
    当 导出 run_stats 结构
    那么 payload MUST 含 schema 标识与 pipeline/stages_total/loaders/nodes 键

  @req:r991 @human
  场景: nodes-survive-second-pipeline
    - 必须成立：假如 共享 accumulator 跨两个 pipeline(首段有 loader 活动)；当 第二段 PIPELINE_START/END 之后；那么 nodes 长度 MUST ≥ 2 且首节点 loaders 非空
    假如 共享 accumulator 跨两个 pipeline(首段有 loader 活动)
    当 第二段 PIPELINE_START/END 之后
    那么 nodes 长度 MUST ≥ 2 且首节点 loaders 非空

  @req:r992 @human
  场景: lite-events-only
    - 必须成立：当 装配 bench accumulator；那么 其 wants/event_types MUST 不包含 ROW_WRITE/FIELD_COMPUTE/RELATION_LOOKUP(除非进入 debug)
    当 装配 bench accumulator
    那么 其 wants/event_types MUST 不包含 ROW_WRITE/FIELD_COMPUTE/RELATION_LOOKUP(除非进入 debug)

  @req:r993 @human
  场景: baseline-empty
    - 必须成立：当 请求 baseline profile；那么 components MUST 为空列表
    当 请求 baseline profile
    那么 components MUST 为空列表

  @req:r993 @human
  场景: bench-factory
    - 必须成立：当 请求 bench profile；那么 components MUST 含可产出 run_stats 的采集器且默认不含 relation 诊断
    当 请求 bench profile
    那么 components MUST 含可产出 run_stats 的采集器且默认不含 relation 诊断

  @req:r994 @human
  场景: debug-warns
    - 必须成立：当 启用 debug/relation 高影响面；那么 系统 MUST 发出警告
    当 启用 debug/relation 高影响面
    那么 系统 MUST 发出警告

  @req:r995 @human
  场景: memory-without-psutil-fails
    - 必须成立：当 bench 请求 memory 且无 psutil；那么 系统 MUST 失败或拒绝该配置而非静默空 peak
    当 bench 请求 memory 且无 psutil
    那么 系统 MUST 失败或拒绝该配置而非静默空 peak

  @req:r996 @human
  场景: bench-output-unchanged
    - 必须成立：假如 同一 demand/workflow 输入；当 baseline 与 bench 各跑一次；那么 CSV 内容哈希 MUST 相等
    假如 同一 demand/workflow 输入
    当 baseline 与 bench 各跑一次
    那么 CSV 内容哈希 MUST 相等

  @req:r997 @human
  场景: sibling-not-in-snapshot
    - 必须成立：当 同时启用 viz 与 run_stats 写出；那么 viz_snapshot.json MUST NOT 内嵌完整 run_stats 对象;MAY 存在旁路 run_stats.json
    当 同时启用 viz 与 run_stats 写出
    那么 viz_snapshot.json MUST NOT 内嵌完整 run_stats 对象;MAY 存在旁路 run_stats.json

  @req:r990 @human
  场景: json-stdlib
    - 必须成立：当 调用 run_stats 落盘辅助；那么 MUST 仅依赖 stdlib json 写入
    当 调用 run_stats 落盘辅助
    那么 MUST 仅依赖 stdlib json 写入

  @req:r991 @human
  场景: last-pipeline-not-full-truth
    - 必须成立：当 文档或 API 注释；那么 MUST 说明勿将共享 PerformanceObserver 末态当作全 workflow 结论
    当 文档或 API 注释
    那么 MUST 说明勿将共享 PerformanceObserver 末态当作全 workflow 结论

  @req:r994 @human
  场景: warn-mentions-alternative
    - 必须成立：当 高影响警告文本；那么 MUST 提及更低漂移替代(如 bench)
    当 高影响警告文本
    那么 MUST 提及更低漂移替代(如 bench)
