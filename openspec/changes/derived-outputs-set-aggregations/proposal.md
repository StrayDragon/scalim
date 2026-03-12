## Why

在把下游业务报表迁移到 Scalim 时,最重的一类“状态壳”来自 set 口径指标:

- `count_distinct`(按用户/证件号/订单号等去重计数)
- “先按 key 去重再计数/汇总”(dedup_by / distinct-on)
- 两阶段聚合(先按实体维度聚一次,再按业务维度聚一次),用于保证口径可解释且可对拍

当前 `derived-outputs` 的内置 `GroupByAggregator` 仅支持 `count/count_true/sum/min/max`,缺少上述 set 口径会导致:

- 业务不得不在 Python 侧维护大块 state,迁移成本高且难复用
- 即使 YAML 层未来暴露 output-composition/derived-outputs authoring surface,也会出现“能编排但算不出指标”的落地断层

因此需要先补齐 streaming-friendly 的 set 口径聚合原语,把最常见的“去重/两阶段”语义下沉到框架内置派生聚合器中.

## Acceptance Case (sanitized)

最小脱敏样例中,汇总 sheet 常见指标形态为:

- `new_paid_users`: `count_distinct(user_id)` 按客服维度统计 distinct 用户数
- `repeat_paid_users`: 两阶段聚合(先按 `user_id` 统计 `pay_order_cnt`,再按 `cs_id` 统计 `count_true(pay_order_cnt>=2)`)

该样例见:
`openspec/changes/derived-outputs-set-aggregations/acceptance/mvp_demo/README.md`

## What Changes

- 扩展 `derived-outputs` 内置聚合指标能力(仍保持“增量累计 + finalize 输出”的模型),新增:
  - `count_distinct(field_id=...)`: 统计 distinct key 数量(支持复合 key)
  - `dedup_by(key_fields=...)`: distinct-on 语义,作为后续计数/求和等指标的前置去重阶段
  - `two_stage_group_by`: 两阶段聚合(例如 stage1 `group_by=id_number`, stage2 `group_by=cs_id`),并固定确定性 tie-break 规则
- 为高基数/高 distinct 风险补齐资源护栏与诊断:
  - 明确 max keys/内存风险告警或 fail-fast 策略(与 `max_groups` 风险告警保持一致的治理口径)
  - meta/audit 侧提供可对拍的聚合配置指纹与关键统计(如 distinct key 数量/截断信息)
- 不改变 YAML DSL(本 change 聚焦执行层聚合原语);YAML authoring surface 作为后续独立 change 推进,并复用本 change 的能力.

## Notes / Suggestions (for future spec)

### Determinism & explainability

- 输出顺序必须稳定:
  - 分组键 `group_by` 的输出排序需与现有 `GroupByAggregator` 一致(稳定排序键),避免对拍误报.
  - 两阶段聚合的 stage1/stage2 均需固定排序与 tie-break 规则,并在 spec 中显式写明.
- `dedup_by` 的冲突策略必须显式:
  - 同一 dedup key 命中多行时,需要明确口径(报错/取 first/取 last/按某个字段 min_by/max_by 等).
  - MVP 建议先支持最小集合: `error|first|last`(确定性且易对拍),复杂策略可后续扩展.

### Guardrails

- `count_distinct` 的内存风险通常高于 `max_groups`:
  - `max_groups` 约束的是“组数量”,而 distinct 约束的是“每组内状态规模”(set).
  - 规范应要求可配置的护栏(例如 `max_distinct` 或统一的资源上限),并规定当上限为 0(不设限)时必须输出明确 warn.
- 当触发护栏时的行为必须可解释且可对拍:
  - fail-fast(推荐用于强口径一致性)
  - 或者允许“截断但记录审计信息”(必须写入 meta/audit 并包含稳定指纹,避免静默偏差)

### Parallel mode boundary

- `count_distinct`/`dedup_by`/两阶段聚合在语义上仍是可交换/可结合的增量累计,但实现需明确其在 `parallel_mode="adaptive"` 下的确定性边界(与现有 derived-outputs spec 的并发边界保持一致口径).

## Capabilities

### New Capabilities
- `derived-outputs-set-aggregations`: 派生输出支持 下游业务 常见的 set 口径聚合原语(`count_distinct`/`dedup_by`/两阶段聚合),保持 streaming-friendly 与可对拍确定性.

### Modified Capabilities
- `derived-outputs`: 扩展内置聚合指标集合与资源护栏/诊断.

## Impact

- 受影响模块:
  - `src/scalim/execution/derived_outputs.py`(新增 metric/aggregator 实现)
  - `src/scalim/execution/output_composition.py`(派生输出装配与 meta/audit 诊断增强)
  - `openspec/specs/derived-outputs/spec.md`(补充 set 口径能力与一致性边界说明)
- 测试:
  - 覆盖 distinct 精确性、复合键、dedup 语义、两阶段确定性与护栏行为
  - 覆盖 meta/audit 诊断与指纹稳定性(对拍友好)
