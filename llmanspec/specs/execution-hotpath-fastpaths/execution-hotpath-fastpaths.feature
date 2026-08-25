# language: zh-CN
# capability: execution-hotpath-fastpaths
# purpose: 在不要求业务改动的前提下，降低 execution 热路径（`compute` / `call_by` / `load_ref` / write-precompute / row-wise fusion）的 per-row 固定开销与中间驻留，并保持既有值语义、可观测性与低内存特性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence] [c10-write-precompute-derived-fields] [c20-compute-expr-rowwise-fusion]
# scope: src/scalim/

功能: execution-hotpath-fastpaths

  @req:r38 @human
  场景: Fastpaths are default-on and behavior-preserving
    - 系统 MUST 默认启用面向执行热路径的 fastpaths。对外 MUST 保持：写出目标字段的值语义、异常类别、以及在未改变物化时机时的事件顺序/边界。允许将“仅用于最终写出、且无 late 子图外消费者”的派生字段物化时机从 compute 段延后到写出前（write-precompute），但写出值 MUST 与延后前一致。允许在安全外壳内对同 deps 派生字段做 row-wise 融合（见 `execution-compute-rowwise-fusion`）；外壳外 MUST 回退 field-major。

  @req:r282 @human
  场景: Compute evaluation preserves name shadowing semantics
    - 在 `compute` 表达式中，依赖字段名与安全函数名冲突时（例如 `len` / `sum`），系统 MUST 保持“字段值优先”的解析语义不变。

  @req:r406 @human
  场景: Compute audit mode semantics remain unchanged
    - 系统 MUST 保持既有 compute 审计模式语义不变： - `audit_mode="none"`：不记录字段值/结果 - `audit_mode="redacted"`：仅记录表达式 hash、字段名与结果类型，不记录字段值与结果原文 - `audit_mode="full"`：仅在显式解锁条件满足时启用，并可能记录敏感数据

  @req:r501 @human
  场景: call_by ctx injection is conditional and minimal
    - 系统 MUST 将 `$ctx` / `$ctx.<attr>` 作为“受控且可选”的上下文注入能力： - 当 `call_by` 参数中未使用 `$ctx` / `$ctx.<attr>` 时，系统 MUST NOT 要求用户函数接受 `ctx` 参数，也 MUST NOT 在执行期 per-row 构造 ctx 对象。 - 当 `call_by` 参数中使用 `$ctx` / `$ctx.<attr>` 时，系统 MUST 提供 `ComputeCallContextIr`，且仅暴露白名单属性：`row_id` / `batch_num` / `field_id` / `deps` / `values`。

  @req:r579 @human
  场景: Fastpaths keep memory overhead bounded and non-row-linear
    - 系统 MUST 在默认 fastpath 下保持低内存特性： - 常驻缓存 MUST 与“字段数/表达式数/批大小”等固定规模相关 - 系统 MUST NOT 引入按 `row_id`/总行数线性增长且跨批/跨 run 存活的额外缓存或索引结构 - write-precompute 的行内 deps cache MUST 仅绑定当前行（或当前列物化）生命周期，MUST NOT 跨行/跨批驻留

  @req:r950 @human
  场景: Write-precompute late fields are auto-selected
    - 系统 MUST 自动识别可延迟物化（late）的派生字段，且 MUST NOT 引入新的 YAML/`virtual`/`lazy` 开关。字段 `f` 仅当同时满足以下条件时 MAY 进入 late 集合： (1) `f` 属于最终写出目标； (2) Plan/IR 显式依赖图中不存在 late 子图以外的消费者（其它非 late 派生、LoadRef `from_field`/join key 等）； (3) `f` 为 `compute_expr`，或为不需要 `$ctx`/`ctx_attr` 的 `call_by`； (4) `f` 的依赖在写出点可获得（含同属 late 子图且可拓扑排序的依赖）。不确定时系统 MUST NOT 将 `f` 标为 late（保守早算）。

  @req:r951 @human
  场景: Late call_by with ctx is forbidden
    - 系统 MUST NOT 将需要 `$ctx` / `$ctx.<attr>` 注入的 `call_by` 字段标为 late；此类字段 MUST 留在既有 compute 段执行。

  @req:r952 @human
  场景: Late materialization happens at write for row and column sinks
    - 对 late 字段，系统 MUST 在 compute 算子段跳过其求值，并在写出前物化： - 行 sink：在 `write_row` / `write_row_aligned`（或等价行写出）之前按 late 子图拓扑计算，结果写入待写出行；默认 MUST NOT 将 late 结果写回 `BatchContext`。 - 列 sink：在写出该 late 列之前物化该列（及为写出该列所必需的尚未物化的 late 依赖列）；写完后默认可不驻留。 - late→late 链式依赖 MUST 按拓扑顺序物化；列路径 MUST 在依赖方写完前保留必要的中间 late 列。

  @req:r953 @human
  场景: Write-precompute preserves call counts and event phase meta
    - 对 late 的 `call_by`/`compute_expr`，系统 MUST 保持每个目标字段每个输入行的计算器/表达式求值次数与早算路径一致（不得因 late 合并多次调用为一次）。当 instrumentation 订阅 `FIELD_COMPUTE` 时，系统 MUST 仍发出对应事件，并 MAY 在事件 meta 中标注 `scalim_compute_phase` 为 `operator` 或 `write_precompute`；未订阅时 MUST NOT 因 phase 标注引入额外可观测税。

  @req:r954 @human
  场景: Fast-fail discards partial write-precompute output
    - 当 `compute_mode`/`guardrails` 为 `fast_fail`（或等价快速失败）且 write-precompute 或早算路径计算失败时，系统 MUST 报错并对 sink 执行 discard/回滚，MUST NOT 将半成品当作最终可用输出。`quiet`（或等价）路径 MUST 保持既有按格降级语义并允许正常收尾。

  @req:r955 @human
  场景: Row-wise fusion cross-ref
    - 系统 MAY 在默认 fastpath 下启用 `execution-compute-rowwise-fusion` 所述 row-wise 融合；融合的候选规则、安全外壳、值/调用次数等价与内存有界 MUST 以该 capability 为 SSOT。本 requirement 仅作交叉引用，MUST NOT 与之冲突。
  @req:r38 @human
  场景: same-inputs-yield-same-outputs
    - 必须成立：当 使用同一份 `DemandIr`、同一批 main rows 与相同 runtime bindings 执行；那么 目标字段的值 MUST 与 fastpath 引入前一致
    当 使用同一份 `DemandIr`、同一批 main rows 与相同 runtime bindings 执行
    那么 目标字段的值 MUST 与 fastpath 引入前一致
  @req:r282 @human
  场景: field-name-shadows-builtin-function-name
    - 必须成立：假如 表达式依赖字段名为 `len`，且表达式引用 `len`；当 运行 `compute` 求值；那么 求值 MUST 使用字段 `len` 的值而不是安全函数 `len`
    假如 表达式依赖字段名为 `len`，且表达式引用 `len`
    当 运行 `compute` 求值
    那么 求值 MUST 使用字段 `len` 的值而不是安全函数 `len`
  @req:r406 @human
  场景: full-audit-requires-explicit-unlock
    - 必须成立：当 compute 以 `audit_mode="full"` 初始化且未设置解锁环境变量；那么 系统 MUST fail-fast 并拒绝启动 full 模式
    当 compute 以 `audit_mode="full"` 初始化且未设置解锁环境变量
    那么 系统 MUST fail-fast 并拒绝启动 full 模式
  @req:r501 @human
  场景: call-by-without-ctx-does-not-require-ctx-argument
    - 必须成立：假如 call_by 仅使用字段参数（不包含 `$ctx`/`$ctx.<attr>`）；当 执行派生字段计算；那么 用户函数 MUST 可采用不包含 `ctx` 的签名并成功运行
    假如 call_by 仅使用字段参数（不包含 `$ctx`/`$ctx.<attr>`）
    当 执行派生字段计算
    那么 用户函数 MUST 可采用不包含 `ctx` 的签名并成功运行

  @req:r501 @human
  场景: call-by-with-ctx-receives-computecallcontextir
    - 必须成立：假如 call_by 参数包含 `$ctx` 或 `$ctx.<attr>`；当 执行派生字段计算；那么 系统 MUST 传入 `ctx=ComputeCallContextIr(...)`
    假如 call_by 参数包含 `$ctx` 或 `$ctx.<attr>`
    当 执行派生字段计算
    那么 系统 MUST 传入 `ctx=ComputeCallContextIr(...)`
  @req:r579 @human
  场景: no-persistent-per-row-caches-are-introduced
    - 必须成立：当 执行处理大量行数据的报表；那么 执行运行时中 MUST NOT 出现以 `row_id` 为 key 的跨批次常驻缓存结构
    当 执行处理大量行数据的报表
    那么 执行运行时中 MUST NOT 出现以 `row_id` 为 key 的跨批次常驻缓存结构
  @req:r950 @human
  场景: output-only-derived-may-be-late
    - 必须成立：假如 存在仅被最终写出消费、不被其它派生/LoadRef 依赖的 `compute_expr` 字段；当 规划/执行识别 late 集合；那么 该字段 MUST 被允许标为 late（或等价延迟物化）
    假如 存在仅被最终写出消费、不被其它派生/LoadRef 依赖的 `compute_expr` 字段
    当 规划/执行识别 late 集合
    那么 该字段 MUST 被允许标为 late（或等价延迟物化）

  @req:r950 @human
  场景: consumed-derived-must-not-be-late
    - 必须成立：假如 派生字段被另一派生或 LoadRef `from_field` 显式依赖；当 识别 late 集合；那么 该字段 MUST NOT 被标为 late
    假如 派生字段被另一派生或 LoadRef `from_field` 显式依赖
    当 识别 late 集合
    那么 该字段 MUST NOT 被标为 late
  @req:r951 @human
  场景: ctx-call-by-stays-eager
    - 必须成立：假如 派生字段为含 `$ctx` 的 `call_by`；当 识别 late 集合；那么 该字段 MUST NOT 被标为 late
    假如 派生字段为含 `$ctx` 的 `call_by`
    当 识别 late 集合
    那么 该字段 MUST NOT 被标为 late
  @req:r952 @human
  场景: row-and-column-late-chains-materialize-in-topo-order
    - 必须成立：假如 late 子图存在 late→late 链且分别走行写出与列写出；当 执行写出；那么 系统 MUST 按拓扑物化且写出值与全量早算一致
    假如 late 子图存在 late→late 链且分别走行写出与列写出
    当 执行写出
    那么 系统 MUST 按拓扑物化且写出值与全量早算一致
  @req:r953 @human
  场景: late-call-by-keeps-per-row-call-count
    - 必须成立：假如 无 ctx 的 late `call_by` 字段与早算对照；当 执行完整写出；那么 instrumented 计算器每行调用次数 MUST 与早算路径相同
    假如 无 ctx 的 late `call_by` 字段与早算对照
    当 执行完整写出
    那么 instrumented 计算器每行调用次数 MUST 与早算路径相同
  @req:r954 @human
  场景: fast-fail-discards-sink-on-late-error
    - 必须成立：假如 `fast_fail` 下 write-precompute 计算抛错；当 执行失败收尾；那么 系统 MUST discard sink 且 MUST NOT 留下可用最终产出
    假如 `fast_fail` 下 write-precompute 计算抛错
    当 执行失败收尾
    那么 系统 MUST discard sink 且 MUST NOT 留下可用最终产出
  @req:r955 @human
  场景: fusion-delegates-to-rowwise-fusion-spec
    - 必须成立：当 存在同 deps 无 ctx `call_by` 候选组且安全外壳允许；那么 融合行为 MUST 遵循 `execution-compute-rowwise-fusion`
    当 存在同 deps 无 ctx `call_by` 候选组且安全外壳允许
    那么 融合行为 MUST 遵循 `execution-compute-rowwise-fusion`
