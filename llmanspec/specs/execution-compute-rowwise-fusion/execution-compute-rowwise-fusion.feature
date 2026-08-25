# language: zh-CN
# capability: execution-compute-rowwise-fusion
# purpose: 在 compute 段对满足约束的派生字段做 row-wise / 同依赖复用融合，降低 N×M 框架税；保持值语义与每字段每行计算器调用次数；安全外壳外回退 field-major。 [c20-compute-expr-rowwise-fusion]
# scope: src/scalim/

功能: execution-compute-rowwise-fusion

  @req:r960 @human
  场景: Row-wise fusion groups are auto-selected
    - 系统 MUST 在同一 compute segment（pre-ref 或 post-ref）内自动识别 fusion group，且 MUST NOT 引入新的 YAML/`call_groups` 开关。字段进入同一 group 当且仅当同时满足：(1) 成员为 `compute_expr` 或无 `$ctx`/`ctx_attr` 的 `call_by`；(2) 组内字段互不依赖；(3) 组内依赖集合完全相同（Q1）；(4) 通过本 spec 安全外壳。不确定时 MUST NOT 融合（回退 field-major）。

  @req:r961 @human
  场景: Safety shell disables fusion
    - 当任一条件成立时，系统 MUST 对该 segment / 候选组禁用融合并回退 field-major：`compute_mode`/`guardrails` 为 `fast_fail`；instrumentation `wants(FIELD_COMPUTE)` 或 `wants(OPERATOR_SPAN)`；sink 为列式（`IColumnSink` 或等价，Q2-B）；组内任一字段的实验性 `call_by` memo 对该字段生效（Q2b）。含 `$ctx`（`call_ctx_key`）或 `is_constant_compute` 的字段 MUST NOT 进入 fusion group。

  @req:r962 @human
  场景: Row sinks may fuse including streaming
    - 对行 sink（含 streaming 与非流式行写出），系统 MAY 在安全外壳内启用融合。对列 sink，系统 MUST NOT 融合（Q2-B）。

  @req:r963 @human
  场景: Fusion preserves values and call counts
    - 融合路径 MUST 保持目标字段值与 field-major 路径一致。对组内每个 `(field, row)`，计算器/`compute_expr` 求值次数 MUST 等于 field-major（`calc_calls == N×M`，Q3）；系统 MUST NOT 将多个不同 calculator 隐式合并为一次调用。

  @req:r964 @human
  场景: Fusion memory stays bounded
    - 融合路径的额外缓冲 MUST 与字段数/组大小/可选固定 tile 相关；峰值 RSS 相对 field-major MUST 满足变更门槛（≤ +10%）。系统 MUST NOT 引入按总行数线性且跨批存活的融合缓存。

  @req:r965 @human
  场景: Fusion observability is optional and low-tax
    - 系统 MAY 记录融合诊断（如 `fused_group_size` / `disabled_reason`，含 `memo` / `column_sink` / `ctx` / `fast_fail` / `wants_events`）。未启用诊断时 MUST NOT 因融合引入可观测税。融合 MUST NOT 改变未订阅时的对外事件契约；当 `wants(FIELD_COMPUTE|OPERATOR_SPAN)` 时 MUST 禁用融合（见 r961）。

  @req:r966 @human
  场景: Fusion only applies to early compute segment fields
    - row-wise fusion MUST 仅作用于仍在 compute 算子段求值的字段集合。write-precompute（late）字段的行内 deps 复用 MUST 由 write-precompute 路径负责，MUST NOT 在本能力中重复实现第二套行内融合引擎。

  @req:r967 @human
  场景: Hotpath default-on aligns with fusion shell
    - 在 `execution-hotpath-fastpaths` 默认开启前提下，本能力的默认行为 MUST 与安全外壳一致：外壳内可融合；外壳外 ≡ field-major。
  @req:r960 @human
  场景: identical-deps-form-one-group
    - 必须成立：假如 同一 segment 内多个无 ctx `call_by` 字段依赖集合完全相同且互不依赖；当 规划/执行识别 fusion group；那么 这些字段 MUST 被允许进入同一 fusion group
    假如 同一 segment 内多个无 ctx `call_by` 字段依赖集合完全相同且互不依赖
    当 规划/执行识别 fusion group
    那么 这些字段 MUST 被允许进入同一 fusion group

  @req:r960 @human
  场景: overlapping-but-unequal-deps-not-fused
    - 必须成立：假如 两字段依赖集合有重叠但不完全相同；当 识别 fusion group；那么 系统 MUST NOT 将二者融为同一组（第一期 Q1）
    假如 两字段依赖集合有重叠但不完全相同
    当 识别 fusion group
    那么 系统 MUST NOT 将二者融为同一组（第一期 Q1）
  @req:r961 @human
  场景: fast-fail-disables-fusion
    - 必须成立：假如 `fast_fail` 开启且存在本可融合的候选组；当 执行 compute 段；那么 系统 MUST 回退 field-major（不融合）
    假如 `fast_fail` 开启且存在本可融合的候选组
    当 执行 compute 段
    那么 系统 MUST 回退 field-major（不融合）

  @req:r961 @human
  场景: field-compute-wants-disables-fusion
    - 必须成立：假如 instrumentation wants `FIELD_COMPUTE`；当 执行 compute 段；那么 系统 MUST 不融合
    假如 instrumentation wants `FIELD_COMPUTE`
    当 执行 compute 段
    那么 系统 MUST 不融合

  @req:r961 @human
  场景: ctx-call-by-excluded-from-group
    - 必须成立：假如 某字段 `call_by` 需要 `$ctx`；当 识别 fusion 候选；那么 该字段 MUST NOT 进入 group
    假如 某字段 `call_by` 需要 `$ctx`
    当 识别 fusion 候选
    那么 该字段 MUST NOT 进入 group

  @req:r961 @human
  场景: memo-enabled-field-disables-whole-group
    - 必须成立：假如 组内一字段 EXP call_by memo 生效；当 识别/执行融合；那么 整组 MUST 禁用融合
    假如 组内一字段 EXP call_by memo 生效
    当 识别/执行融合
    那么 整组 MUST 禁用融合
  @req:r962 @human
  场景: row-streaming-may-fuse
    - 必须成立：假如 行 streaming sink 且安全外壳允许；当 执行；那么 系统 MAY 融合且写出值 MUST 与 field-major 一致
    假如 行 streaming sink 且安全外壳允许
    当 执行
    那么 系统 MAY 融合且写出值 MUST 与 field-major 一致

  @req:r962 @human
  场景: column-sink-never-fuses
    - 必须成立：假如 列 sink 且存在同 deps 候选；当 执行；那么 系统 MUST NOT 融合
    假如 列 sink 且存在同 deps 候选
    当 执行
    那么 系统 MUST NOT 融合
  @req:r963 @human
  场景: calc-calls-equal-n-times-m
    - 必须成立：假如 N 行 × M 个同 deps 薄 `call_by`；当 融合路径与 field-major 对拍；那么 两边 `calc_calls` MUST 均为 N×M 且值一致
    假如 N 行 × M 个同 deps 薄 `call_by`
    当 融合路径与 field-major 对拍
    那么 两边 `calc_calls` MUST 均为 N×M 且值一致
  @req:r964 @human
  场景: no-cross-batch-fusion-row-cache
    - 必须成立：当 在多 batch 行路径上启用融合；那么 系统 MUST NOT 保留跨 batch 的按行融合缓存
    当 在多 batch 行路径上启用融合
    那么 系统 MUST NOT 保留跨 batch 的按行融合缓存
  @req:r965 @human
  场景: disabled-reason-may-be-logged
    - 必须成立：假如 融合因 `column_sink` 或 `memo` 禁用且诊断开启；当 执行；那么 系统 MAY 暴露对应 `disabled_reason`
    假如 融合因 `column_sink` 或 `memo` 禁用且诊断开启
    当 执行
    那么 系统 MAY 暴露对应 `disabled_reason`
  @req:r966 @human
  场景: late-fields-not-double-fused
    - 必须成立：假如 字段属于 write-precompute `late_fields`；当 执行；那么 该字段 MUST 不由本 row-wise fusion 引擎在 late 路径再次融合调度
    假如 字段属于 write-precompute `late_fields`
    当 执行
    那么 该字段 MUST 不由本 row-wise fusion 引擎在 late 路径再次融合调度
  @req:r967 @human
  场景: shell-off-equals-field-major
    - 必须成立：假如 安全外壳关闭融合；当 执行；那么 行为 MUST 等价于既有 field-major fastpath
    假如 安全外壳关闭融合
    当 执行
    那么 行为 MUST 等价于既有 field-major fastpath
