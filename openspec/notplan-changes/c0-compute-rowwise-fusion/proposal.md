## Status (2026-04-30)

本提案位于 `openspec/notplan-changes/`，用于沉淀候选方向；尚未进入 active change 工作流，默认不交付、不承诺实现时间。建议在 `c0`（执行热路径 micro-opt）验收后，再评估是否需要引入更激进的“算子融合”。

## Why

当前派生字段执行的核心形态更接近“按字段列式执行”：

```
for derived_field in topo_order:
  for row in batch_rows:
    dep_args = tuple(get_field_value(dep, row) for dep in deps)
    result = calculator(*dep_args)
    set_field_value(field, row, result)
```

当派生字段数量很大、且大量字段依赖高度重叠（例如都依赖同一组主表字段/同一组 ref 字段）时，会出现显著的重复成本：

- **同一行重复读取相同 deps**：`get_field_value` 次数约为 `行数 × Σ deps(field)`。
- **同一行重复的 Python 调度/分支**：每个字段都有一套 try/except、transform、写回逻辑。

如果能把一组互不依赖的派生字段融合为一个 row-wise 计算循环，则理论上可把 deps 读取次数降为 `行数 × deps(union)`，在“字段很多且 deps 重叠高”的场景收益显著，并且不要求业务侧改写函数为 batch API（保持 row-mode）。

## What Changes

引入一个**内部优化**：`row-wise compute fusion`（按行融合计算）。

### 1) 融合候选（candidate groups）

在一个 compute segment（pre-ref 或 post-ref）内，选取满足约束的一组派生字段，组成 fusion group：

- **字段间无依赖**：组内字段之间不存在依赖边（否则必须保持严格拓扑序，收益会下降且语义更敏感）。
- **仅限 compute_expr（建议）**：第一阶段建议只融合 `compute` 表达式字段，不包含 `call_by`（`call_by` 可能有副作用与 `$ctx`，且错误语义更难保持完全等价）。
- **deps 高重叠**：组内字段的 deps 集合重叠度高（可先采用“完全相同 deps”的强约束，后续再放宽到“高重叠”并引入 union 索引映射）。

### 2) 执行形态

对每个 fusion group：

- 预计算 `union_deps`（组内所有字段 deps 的并集）与每个字段的 `dep_indices`（其 deps 在 union 中的位置）。
- 逐行：
  - 一次性读取 `union_deps` 对应的值；
  - 依次计算组内字段并写回 context（必要时应用 value_transform）。

这会把“deps 读取”从 `Σ deps(field)` 降到 `deps(union)`，并把一些热路径属性查找/分支从“每字段每行一次”降为“每组每行一次”。

## Semantics: What Can Change (必须提前写清楚)

该优化的核心风险不在“值是否能算出来”，而在“跨字段执行顺序”变化带来的外部可见差异：

1) **事件顺序变化**（当订阅 `FIELD_COMPUTE` / `OPERATOR_SPAN` 时）：
   - 原先：field-major（先算完字段 A 的所有行，再算字段 B 的所有行）。
   - 融合后：row-major（同一行内按字段顺序依次算 A、B、C…，再进入下一行）。
2) **fast_fail 触发点变化**：
   - 在 `compute_mode="fast_fail"` 下，首个异常的“字段/行”可能不同，从而影响“失败前已经完成的计算/已写出的行前缀”。
3) **副作用顺序**：
   - 若融合包含 `call_by`（不推荐），用户函数的副作用发生顺序可能改变（即使调用次数不变）。

因此：即使不引入新 DSL，这也应被视为“语义敏感的执行调度变更”，需要明确的启用边界。

## Recommended Safety Envelope（建议的无争议版本）

为了尽可能做到“业务零改动 + 无争议”，建议把第一阶段的融合限定在一个足够安全的 envelope 内：

- **仅 compute_expr**（不包含 call_by）。
- **禁用在 fast_fail**：当 `guardrails.effective_compute_mode()=="fast_fail"` 时不启用（直接回退原路径）。
- **禁用在观测开启**：当 `instrumentation.wants(FIELD_COMPUTE)` 或 `instrumentation.wants(OPERATOR_SPAN)` 为 true 时不启用（避免事件顺序变化）。
- **优先仅 batch 非流式**：先在非 streaming 模式启用；对 streaming 模式的“行就绪/写出时机”变化单独评估（否则会改变写出节奏与已写前缀语义）。

在上述 envelope 内，融合对外可见差异被压缩到最小：既不改变事件序列（因为未订阅），也不改变 fast_fail 行为（因为禁用），且 compute_expr 预期为纯计算。

## Observability Plan（若未来要扩大 envelope）

若希望在“观测开启”或“streaming”场景也启用，需要明确新的可观测性与契约：

- 事件层：
  - 允许 `FIELD_COMPUTE` 的顺序从 field-major 变为 row-major，或
  - 引入额外标注（例如 `Event.meta["scalim_fused_group_id"]`），并在 docs/specs 明确“顺序不稳定/仅局部有序”的边界。
- fast_fail：
  - 明确在融合模式下“失败前写出前缀”的不可预测性（或强制禁用融合）。
- 更强的等价方案（有成本）：
  - tile-buffer：按小块 rows（例如 64/256 行）进行融合计算并在块内维持 field-major 事件顺序，但需要额外内存缓冲（与 tile 大小线性相关）。

## Capabilities

### New (candidate)
- `execution-compute-rowwise-fusion`: 在受限 envelope 下融合一组 compute_expr 派生字段的执行循环，以减少重复 deps 读取与调度开销。

### Modified (candidate)
- `execution-guardrails`: 需要把“是否允许融合”的判定与 guardrails mode/streaming 写出策略联动。
- `events-operator-span`: 若未来希望对 fusion group 统计耗时，需要定义 `operator_type` / meta 标注的口径。

## Impact

**收益上限**：

- 对 deps 重叠极高的字段簇，`get_field_value` 次数可从 `Σ deps(field)` 降到 `deps(union)`（按行）；当字段数很大、deps 重叠高时收益显著。

**风险/成本**：

- 语义敏感：事件顺序、fast_fail 触发点、streaming 写出节奏都可能变化。
- 工程复杂度：要么扩大 envelope 就必须写清楚契约，要么保持 envelope 严格就会限制适用面。

## Alternatives

1) **仅做 c0 类 micro-opt**：不改执行形态，只减少 ctx/dep payload 分配与热点属性查找（最稳妥，收益也有限）。
2) **写出前延迟物化（方案 A）**：只对 output-only derived 生效，语义更易治理，且常常同时省内存（见 `c0-write-precompute-derived-fields`）。

