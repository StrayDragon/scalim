## Status (2026-04-30)

本提案位于 `openspec/notplan-changes/`，用于沉淀候选方向；尚未进入 active change 工作流，默认不交付、不承诺实现时间。建议在 `c0`（执行热路径 micro-opt）验收基准后，再决定是否转正推进。

## Why

在“字段很多但单条逻辑很薄”的报表型 workload 中，执行层的固定开销往往由下面两类重复工作主导：

1) **同一行重复读取依赖值**：当前执行形态更接近“按字段列式执行”（`for field: for row: get deps → calc → set`）。当输出字段很多、且依赖高度重叠时，同一行会反复 `get_field_value` 读取相同 deps。
2) **输出专用字段的提前物化**：大量派生字段只用于最终写出/展示（`target_fields`），并不参与后续 join/中间计算，但仍会在 compute 阶段提前计算并写入 `BatchContext`，产生：
   - 不必要的 `set_field_value` 写入开销；
   - 不必要的上下文存储（内存峰值/驻留更高，尤其在 batch 非流式模式下）。

如果能把“仅用于写出”的派生字段改为 **写出前按行即时计算（late materialization）**，则可在不要求业务侧改 YAML/代码的前提下：

- 把“同一行多个输出字段”合并为一次 deps 取值（row-local cache），显著降低查找次数；
- 避免把这些字段写入 `BatchContext`，降低内存与写回开销。

## What Changes

引入一个**内部优化**：`write-precompute`（写出前计算/延迟物化）。

### 1) 识别“输出专用派生字段”（candidates）

在规划/运行时绑定阶段识别一组派生字段 `late_fields`，满足：

- 字段属于 `plan.target_fields`（最终输出目标字段）；并且
- 字段不被任何后续计算/关联步骤消费（不作为其他 derived 的依赖；不被 `load_ref.lookup_steps` 使用；不属于 `plan.key_fields`）；并且
- 字段的依赖在“写出点”可获得（依赖来自 main/ref 已加载字段，或来自同样被纳入 late 子图的字段）。

> 注：这一步需要一个明确且可审计的“消费者判定”规则。建议只从 ExecutionPlan/IR 的显式依赖关系推导，避免引入隐式约定。

### 2) 运行时执行形态（按 sink 类型分流）

**Row sink（含 streaming）**：

- 在行写出时（`write_row` / `write_row_aligned` 之前）对该行计算 `late_fields`。
- 计算结果直接写入“待写出行数据”（dict 或 values list），默认不落入 `BatchContext`（减少内存与写回开销）。
- 使用 row-local cache（只在当前行生存）复用 deps：同一行多个 late 字段共享一次 `get_field_value` 结果。

**Column sink / column write**：

- 先不覆盖（默认禁用/不做），或仅在后续单独讨论“列写出前批量生成列数据”的实现；否则容易把 row-optimized 逻辑变成 N×列扫描。

### 3) “late 子图”计算顺序

若 late 字段之间存在依赖，应在写出前以“子图内拓扑序”计算，且只在当前行范围内保留中间结果（仍为 row-local，不写回上下文）。

## Observability / Events

该优化会把部分字段的计算从 `COMPUTE` 算子阶段移动到 `WRITE_*` 阶段。为避免观测混淆，建议明确区分两类“字段计算发生点”：

- **operator compute**：现有 compute 算子内产生的计算
- **write-precompute**：行写出前即时产生的计算

推荐的事件策略（不新增事件类型，尽量保持对外契约稳定）：

1) 仍发出 `FIELD_COMPUTE`（否则会让现有订阅方丢事件）。
2) 为区分来源，在事件中增加一个稳定标记：
   - 优先方案：通过 `Event.meta` 传递 `scalim_compute_phase="operator"|"write_precompute"`（对 `Observer` / `hook.on_event(Event)` 可见）。
   - 若需要让 typed hook 也可区分：考虑为 `FieldComputeEvent` 增加可选字段 `phase`（需要评估对外兼容性与文档治理成本）。
3) `OPERATOR_SPAN` 的口径：
   - 可选：对 write-precompute 也发出 `OPERATOR_SPAN`，但 `operator_type` 建议使用新字符串（例如 `write_precompute`），避免与 compute 算子统计混淆；或继续使用 `compute` 但通过 `meta` 标注阶段。

## Semantics / Guardrails

需要在 proposal 中把“不会变”说清楚，避免后续讨论歧义：

- **字段值语义**：最终写出的值与原先“先写入 context 再写出”的逻辑一致。
- **错误语义**：沿用现有 compute 错误处理与 guardrails（quiet/fast_fail）：
  - quiet：该字段写出 `None`，并按既有规则发出 error/guardrail 记录。
  - fast_fail：在写出前的计算中触发同样的 fail-fast 行为（可能导致部分行已经写出/未写出，需在 spec 中明确）。
- **副作用边界**：若 late 字段包含 `call_by`，其副作用“发生时机”会后移（但次数不变）。这是一个必须在转正时写入 spec 的行为差异点。

## Capabilities

### New (candidate)
- `execution-write-precompute-derived-fields`: 允许框架将“仅用于最终写出”的派生字段延迟到写出前计算，支持 row-local deps 复用与不落 context 写回。

### Modified (candidate)
- `events-field-compute`: 字段计算事件增加“发生阶段/来源”的可区分能力（meta 或 payload 字段）。
- `planning-target-fields`: 需要定义“输出专用字段”的消费者推导规则，以及对 streaming readiness 的影响边界。

## Impact

**收益上限（理想场景）**：

- 对输出字段很多且 deps 重叠高的场景，可把 `get_field_value` 次数从 `Σ deps(field)` 降为 `deps(union)`（按行），并减少 `set_field_value` 与上下文存储。

**风险/成本**：

- 观测/诊断：`FIELD_COMPUTE` 发生在 write 阶段，可能改变统计口径与时间线；需要事件标注策略。
- fast_fail：失败点可能从“compute 阶段”移动到“write 阶段”，对流式输出的“已写出前缀”可能产生差异。
- 复杂度：需要在 planning/runtime/execution/write path 之间协同维护 late 子图与 readiness。

## Alternatives

1) **仅在无人订阅时启用**：当 `instrumentation.wants(FIELD_COMPUTE/OPERATOR_SPAN)` 为 false 且 guardrails 不为 fast_fail 时，自动启用 write-precompute；否则回退到原语义路径。优点是治理成本低；缺点是可预测性差（同一配置在不同观测开关下性能不同）。
2) **显式 profile/option**：后续若引入 `c1` 的 performance profiles，可把该优化作为 `speed` 或 `experimental_speed` 的可选项，确保行为差异是显式 opt-in。

