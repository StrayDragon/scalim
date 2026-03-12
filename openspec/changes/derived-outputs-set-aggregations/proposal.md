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

本 change 仅扩展执行层的派生聚合原语(IR/Python-only),不引入 YAML authoring surface 变更.

### MVP 新增能力(可实现且可对拍)

1) **新指标**: `count_distinct`
- 作为内置 metric op 扩展到 `GroupByAggregator`(仍保持“增量累计 + finalize 输出”模型).
- 支持:
  - 单字段 distinct:`count_distinct(field_id="user_id")`
  - 复合 key distinct:`count_distinct(field_ids=("cs_id","user_id"))`
- `max_distinct` 护栏(默认 per-group): 对每个 group key 的 distinct key 数限制上限(与 `max_groups` 分工明确).

2) **新阶段**: `dedup_by`(distinct-on)
- 作为派生聚合 pipeline 的“前置去重阶段”:
  - `dedup_by(key_fields=("cs_id","user_id"), on_conflict=...)` 先将流压缩为唯一 key 的代表行
  - 然后再执行后续 `group_by + metrics`(count/sum/count_distinct 等)
- 冲突策略(MVP):
  - `error`(默认,强口径可对拍)
  - `first|last`(显式依赖输入顺序;仅 `parallel_mode="seq"` 允许,`adaptive` 下 fail-fast)

3) **新聚合器**: `two_stage_group_by`(两阶段聚合)
- stage1: 先按实体维度聚合(例如 `user_id`/`id_number`)
- stage2: 再按业务维度聚合(例如 `cs_id`)
- stage1→stage2 的数据流为 “stage1 finalize 输出行(稳定排序) → stage2 accumulate”(保证确定性).
- 条件计数采用**结构化 predicate**(不引入表达式字符串),MVP 支持 6 种比较: `>= > == != <= <`(可对拍且可指纹化).

4) **资源护栏 + 诊断(meta/audit)**
- 新增 `max_distinct`:
  - `max_distinct=0` 表示不设上限,但 MUST 输出一次明确 warn(不改变语义).
  - 默认溢出策略为 `error`(fail-fast),并写入审计信息.
- meta/audit 增强:
  - 写入派生聚合配置的稳定指纹(`fingerprint`)与关键统计(如 distinct key 数/冲突次数/触发护栏信息).

### 不做的事(范围边界)
- 不改变 YAML DSL(本 change 聚焦执行层聚合原语);YAML authoring surface 作为后续独立 change 推进,并复用本 change 的能力.
- MVP 不提供 `on_overflow="truncate"`(避免静默错数);未来若引入,仅允许 deterministic 的 `truncate_stable` 并必须记录审计信息.
- MVP 不引入近似 distinct(HLL/Theta)与落盘 spill;这些作为后续扩展点.

## Decisions (resolved defaults)

为保证“可实现 + 可对拍 + 可扩展”,本 change 的默认行为固定如下:

- `max_distinct`:
  - `count_distinct`: **per-group** 上限(每个 group key 一套 distinct 状态)
  - `dedup_by`: **global** 上限(该 stage 的 dedup key 总量上限)
- `on_overflow`:
  - MVP 仅支持 `error`(fail-fast)并输出结构化审计;不支持截断.
- `count_distinct` 缺失值:
  - distinct key 为 `None` 时默认 **忽略**(对齐 SQL `COUNT(DISTINCT)` 的 `NULL` 语义)
  - 空字符串 `""` 默认作为普通值参与 distinct
  - 未来扩展点: `exclude_values`/`null_policy` 等更泛化的过滤规则(见下文 Extensibility)
- `two_stage_group_by` 条件计数:
  - MVP 采用结构化 predicate,支持 6 比较符: `>= > == != <= <`
  - 可选组合: `all`/`any`(AND/OR)作为未来扩展点,但仍要求完全可指纹化.

## Concrete Semantics (MVP)

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
  - 或者允许“截断但记录审计信息”(未来扩展;必须写入 meta/audit 并包含稳定指纹,避免静默偏差)

### Parallel mode boundary

- `count_distinct`/`dedup_by`/两阶段聚合在语义上仍是可交换/可结合的增量累计,但实现需明确其在 `parallel_mode="adaptive"` 下的确定性边界(与现有 derived-outputs spec 的并发边界保持一致口径).
- MVP 规则:
  - `dedup_by.on_conflict=first|last` 属于顺序依赖语义,在 `adaptive` 下 MUST fail-fast,提示切换 `seq` 或改用 `error`.
  - `dedup_by.on_conflict=error` 与 `count_distinct`/`sum` 等可交换聚合可以在 `adaptive` 下工作(前提:实现不依赖输入顺序,且输出排序仅在 finalize 阶段执行).

## IR/Python Configuration (draft, non-YAML)

该 change 不引入 YAML authoring surface,但需要一个清晰可实现的 IR/Python 配置形态.建议实现侧以“stage pipeline”收敛:

- `dedup_by?`(可选) → `group_by(stage1)` → `group_by(stage2)?`(可选) → `rank?`(既有能力)

最小 IR/Python 入口建议包含:

- `DedupBySpec(key_fields, on_conflict, max_distinct)`
- `GroupBySpec(group_by, metrics, max_groups, max_distinct?)`
- `TwoStageGroupBySpec(stage1, stage2)`
- `PredicateSpec(field_id, op, value)`(用于 `count_true(predicate=...)`)

并要求每个派生聚合目标可生成:
- `required_fields()`(用于 demand 字段裁剪)
- `fingerprint_parts()`(用于 meta/audit 指纹)
- `supports_parallel_mode(parallel_mode)`(用于 `adaptive` fail-fast)

## Extensibility (non-MVP, keep deterministic)

在不破坏 MVP 语义的前提下,后续可按同一规律扩展:

- 溢出策略:
  - `truncate_stable`: 仅允许 deterministic 的截断规则(例如按稳定 key/hash 排序取前 N),并必须输出 `dropped_keys_count`/`truncated=true`/fingerprint.
- 去重 tie-break:
  - `min_by/max_by`/`first_by/last_by(order_fields=...)` 以稳定排序字段替代纯输入顺序,从而使其在 `adaptive` 下也可用.
- predicate 扩展:
  - `in/not_in`、`between`、`is_null`、`all/any` 组合,但仍要求完全可指纹化(不引入任意表达式 eval).

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
