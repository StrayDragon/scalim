## Context

现状:
- `derived-outputs` 当前实现提供了内置 `GroupByAggregator`/`RankedGroupByAggregator`,并支持 `count/count_true/sum/min/max` 等可增量累计指标,在 `finalize` 阶段输出结果且排序稳定。
- 下游业务报表迁移到 Scalim 时,最重的一类“状态壳”来自 set 口径指标(去重计数、distinct-on 预去重、两阶段聚合)。若这些语义不下沉到框架内置派生聚合器,业务将不得不在 Python 侧维护大块 state,迁移成本高且难复用。

约束:
- 运行时兼容 Python 3.6。
- 仍保持“增量累计 + finalize 输出”的派生输出模型,并保证输出顺序与 tie-break 规则确定(可对拍)。
- distinct/dedup 状态可能高基数,需要与现有 `max_groups` 类似的资源护栏与明确告警/失败策略,并在 meta/audit 侧提供可对拍诊断信息与稳定指纹。
- 需要明确 `parallel_mode="adaptive"` 下的确定性边界: 仅允许可交换/可结合且结果确定性的内置聚合;否则 fail-fast 并提示切换到 `parallel_mode="seq"`。

## Goals / Non-Goals

**Goals:**
- 扩展 `derived-outputs` 内置聚合能力,新增 set 口径原语:
  - `count_distinct(field_id=...)`(支持复合 key)
  - `dedup_by(key_fields=..., on_conflict=error|first|last)` 作为后续指标计算的前置去重阶段
  - `two_stage_group_by(stage1=..., stage2=...)` 支持常见“两阶段口径”(先实体维度再业务维度)
- 明确并实现确定性规则:
  - 输出行排序与现有 `GroupByAggregator` 对齐(稳定排序键)
  - `dedup_by` 冲突策略显式且可对拍
  - 两阶段聚合 stage1/stage2 的输出顺序与 tie-break 固定且在 spec 中可描述
- 补齐资源护栏与诊断:
  - 为 distinct/dedup 状态提供可配置上限(默认 fail-fast,可选截断但必须写入 meta/audit)
  - `max_distinct=0`(不设上限)时输出一次明确 warn(不改变语义)
  - meta/audit 写入稳定的聚合配置指纹与关键统计(如 distinct key 数量/截断信息)

**Non-Goals:**
- 不改变 YAML DSL authoring surface(本变更仅提供执行层/IR/Python-only 聚合原语),YAML 入口作为后续独立 change 推进并复用本能力。
- 不引入近似 distinct(HLL 等)或落盘/分布式聚合;MVP 聚焦精确口径与可对拍确定性。
- 不在 MVP 支持复杂冲突策略(例如 `min_by/max_by`),仅覆盖 `error|first|last`。

## Decisions

1) **派生聚合配置入口升级(不依赖 YAML)**
- 继续保持 IR/Python-only 配置入口,在 `output_composition` 侧将“派生输出目标”从仅支持 `group_by` 扩展为可表达:
  - `group_by`
  - `dedup_by + group_by`(去重阶段 + 聚合阶段)
  - `two_stage_group_by`(stage1 聚合 → stage2 聚合)
- 在实现上,推荐将派生聚合配置收敛为一个可构建 `IRowAggregator` 的 spec(或工厂)对象,并提供:
  - `required_fields()` 用于 `required_demand_fields` 计算
  - `supports_parallel_mode(parallel_mode)` 用于在构建路由前做 fail-fast 校验
  - `fingerprint_parts()` 用于生成稳定 meta/audit 指纹(不包含 callables)

2) **`count_distinct` 作为内置 metric op**
- 将 `count_distinct` 作为 `GroupBy` 指标的一种 `op`,实现为新的 `_MetricState`:
  - 支持单字段与复合 key(例如 `field_ids=("user_id","id_number")`)。
  - `None` 参与 key 的规则需显式: MVP 建议把 `None` 当作普通值(即 `(None,)` 也是一个 distinct key),避免静默丢数;若业务需要忽略 `None`,可在上游清洗或后续扩展策略开关。
- 护栏:
  - 引入 `max_distinct`(默认 0 表示不设上限)。
  - `max_distinct=0` 时在构建派生目标时输出一次 warn(与 `max_groups=0` 的治理口径一致)。
  - 当 distinct key 数超过上限时:
    - 默认 `on_overflow="error"`(推荐,强口径一致性)。
    - 可选 `on_overflow="truncate"`(必须记录截断统计与指纹;截断的“保留集合”规则必须确定性,例如按稳定 key 排序后取前 N)。

3) **`dedup_by` 作为“前置去重阶段”**
- `dedup_by` 的语义是 distinct-on: 对给定 `key_fields` 选择代表行,并将代表行送入后续聚合指标计算。
- 冲突策略:
  - `error`: 同 key 命中多行直接 fail-fast(用于强一致/对拍)。
  - `first`: 选择确定性的“第一条”(MVP 定义为**输入顺序中的第一条**;在 `parallel_mode="adaptive"` 下由于输入顺序不保证,必须 fail-fast)。
  - `last`: 选择确定性的“最后一条”(同上,依赖输入顺序;在 `adaptive` 下必须 fail-fast)。
- 实现建议:
  - 以“阶段(stage)”实现: `DedupByStage` 维护 key → 代表行(仅保留后续聚合所需字段),并在 `finalize` 时将代表行批量喂给下游聚合器。
  - 该实现可保证 `first/last` 语义清晰,且便于在 meta/audit 侧输出 distinct key 数量与冲突统计。
- 护栏:
  - `dedup_by` 复用 `max_distinct/on_overflow` 治理口径(上限针对 dedup key 数)。

4) **`two_stage_group_by` 以“stage1 finalize → stage2 accumulate”的流水线实现**
- 定义:
  - stage1: 对原始详情流按 `stage1.group_by` 聚合,输出 stage1 行(稳定排序)。
  - stage2: 消费 stage1 行,按 `stage2.group_by` 再聚合输出最终行(稳定排序)。
- 确定性:
  - stage1/stage2 的输出排序均复用现有 `_stable_group_key_tuple` 规则。
  - stage1 输出行作为 stage2 的输入顺序必须固定(即 stage1 finalize 后按稳定排序产出)。
- 配置限制(与 `adaptive` 一致性边界对齐):
  - 若任一阶段包含依赖输入顺序的语义(例如 `dedup_by.on_conflict=first|last`),在 `parallel_mode="adaptive"` 下必须 fail-fast,提示改用 `parallel_mode="seq"` 或改用可交换策略(`on_conflict=error`)。
  - 若需要 stage2 做 `count_true(pay_order_cnt>=2)` 这类条件计数,优先提供**声明式**的最小条件能力(例如 `count_true_gte(field_id, threshold)`),避免引入不可指纹化的复杂 callable/表达式系统。

5) **Meta/Audit 诊断与稳定指纹**
- 复用 `fingerprint_for_meta` 的思路,为每个 derived target 生成稳定指纹:
  - 指纹输入包含: 派生目标 id、聚合类型、group_by、metrics(含 op/字段/参数)、护栏配置(含 `max_groups/max_distinct/on_overflow/on_conflict`)。
  - 指纹刻意不包含可调用对象(callable)与环境相关对象,确保跨进程/跨环境稳定。
- meta 写入建议 key:
  - `derived.<target_id>.fingerprint`
  - `derived.<target_id>.distinct_keys` / `...dedup_keys`
  - `derived.<target_id>.truncated` / `...dropped_keys`
- audit:
  - 当触发 fail-fast/截断等护栏时,写入结构化审计行(避免泄露行内容),并包含 error_type / error_message_hash / 关键计数与指纹。

6) **文档/生成边界与 drift gate**
- 本 change 的 spec 变更以 `openspec/changes/derived-outputs-set-aggregations/specs/derived-outputs/spec.md` 作为 delta spec;同步到主 spec 时通过 OpenSpec 工作流完成,避免手改生成物。
- 若后续需要更新 docs-site 的 `.gen.` 页面或 injected blocks,必须修改 SSOT 并运行 `just gen-docs`。
- 归档/共享前运行 `just openspec-check`(sanitize + `openspec validate --all --strict --no-interactive`)确保工件与规范一致。

## Risks / Trade-offs

- [distinct/dedup 状态高基数导致内存风险] → 提供 `max_distinct` 护栏 + `max_distinct=0` warn + fail-fast(默认)。
- [`dedup_by.first/last` 依赖输入顺序,在 adaptive 下不可保证] → 在 `parallel_mode="adaptive"` 下对该类配置 fail-fast,并在错误信息中给出可操作建议(切 `seq` 或改 `error`)。
- [two-stage 可能需要条件计数/表达式能力] → MVP 先提供最小声明式条件算子(如 `count_true_gte`),避免引入完整表达式语言与指纹不稳定问题。
- [增加配置与实现复杂度] → 通过“stage pipeline + 统一护栏/指纹/诊断”收敛复杂度,并用单元测试覆盖确定性与护栏行为。

## Migration Plan

- 实现阶段:
  1. 增加/升级派生聚合 spec 与 `output_composition` 装配,并打通 `run_parallel_mode` 的 fail-fast 校验。
  2. 实现 `count_distinct` 与 `max_distinct` 护栏(含 warn/审计/指纹)。
  3. 实现 `dedup_by` 阶段与两阶段聚合流水线,补齐确定性规则与测试。
  4. 扩展 meta/audit 输出,保证对拍诊断可用。
- 校验阶段:
  - 运行相关单元测试与 `just qa`。
  - 在归档前运行 `just openspec-check`。

## Open Questions

- `max_distinct` 的语义是否需要区分“每组上限”(per-group)与“全局上限”(global)? MVP 先做全局还是每组更符合现有报表口径?
- `on_overflow="truncate"` 是否需要纳入 MVP? 若需要,截断的确定性规则是否采用“按稳定 key 排序取前 N”(成本更高但确定)还是“按输入顺序取前 N”(更便宜但更依赖顺序)?
- `count_distinct` 对 `None`/空字符串等缺失值是否应默认参与 distinct? 若需要忽略缺失,是否提供显式开关(例如 `ignore_nulls`)?
- `two_stage_group_by` 的条件计数最小算子集合是什么(仅 `>=` 足够,还是需要 `==/!=/<=` 等),以覆盖更多“可对拍”的常见口径?
