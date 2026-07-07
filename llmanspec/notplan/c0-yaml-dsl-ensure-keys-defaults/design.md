## Context

本变更落在两条现有主链路之上：

1) **relation lookup / LoadRef 写回**
- YAML 解析后，source 字段(`SourceFieldConfig`)会被编译为 `FieldIr`，若为 ref 字段则包含 `lookup_steps`。
- 执行期由 `LoadRefOperatorExecutor` 执行 lookup；miss 时在 `execution/executor/operators/load_ref/flow.py` 将 group 内字段写回 `None`。

2) **聚合输出(derived outputs) finalize**
- YAML `outputs[*].aggregate` 会被编译为 derived target，并在 `RouterRowSink.close()` 时通过 `AggregatingRowSink.close()` 执行 `aggregator.finalize_rows()` 后一次性写出。
- `GroupByAggregator` / `RankedGroupByAggregator` 会在 finalize 阶段输出稳定排序后的聚合结果。
- derived outputs 的 `aggregator.diagnostics()` 会被 `RouterRowSink` 收集并写入 meta/audit（这是实现 ensure_keys “补全统计诊断”的最佳落点，不需要引入新的日志/事件管线）。

约束：
- runtime 必须兼容 Python 3.6。
- 安全：`default_by` 必须复用现有 resolver/allowlist 策略，不允许引入“隐式绕过 allowlist”的新入口。
- 文档治理：`*.gen.*` 与 injected blocks 禁止手改；schema 变更必须改 SSOT 并走生成入口。

术语/定义（用于后续自解释）：
- **ref 字段**：声明了 `relation`（或可推断出 `lookup_steps`）的 source 字段；执行期由 LoadRef 写回。
- **relation miss**：该字段在 LoadRef 阶段无法从关联 source 得到 value。包含：外键为 None/无法归一化、任一步 miss、最终 miss。
- **hit 但值为 None**：lookup 命中但 extract 后字段值为 None（字段缺失/明确为 None）。这不是 relation miss。
- **derived output**：声明 `outputs[*].aggregate` 的输出；其结果不是流式产生，而是在 close/finalize 阶段一次性写出。

## Goals / Non-Goals

**Goals:**
- 提供声明式能力覆盖两类高频缺失数据场景：
  - relation miss 的字段级缺省值：`default` / `default_by`
  - 聚合结果缺失 group 的键空间补全：`ensure_keys`
- 保持向后兼容：未声明新字段时语义不变。
- 保持确定性：补全后的输出行顺序稳定、可对拍。
- 保持可治理：新增严格校验与可观测诊断（补全统计、miss/default 统计）。
- 交付时保证“交给别人也能做”：文档必须说明**放在哪里改**、**怎么验证**、**不做什么**。

**Non-Goals:**
- 不引入 FULL OUTER JOIN / join_mode 等全局 join 语义改动。
- v1 不支持在明细输出(detail)上做 ensure_keys（仅对 `aggregate` 的 derived output 生效）。
- v1 不解决“补全行参与聚合(before_aggregate)”；该能力作为未来扩展另开 RFC。
- v1 不把 `default/default_by` 扩展为“对任意 None 做 coalesce”（仅限 relation miss）。

## Clarifications (Deferred Semantics)

本 RFC 中提到的 “before_aggregate” 与 “detail output” 常被误解；这里给出 v1 的明确边界与被 defer 的能力含义，方便实现/评审对齐。

### `after_aggregate`（v1 采用）

`ensure_keys` 在 derived output 的 finalize 阶段运行：
- 先正常聚合得到 rows（包含 metrics / post fields / rank_fields 等）
- 再从维度源拿到“期望键集合”，对缺失 keys 追加“补全行”

优点：
- **成本低**：不改 main_source 行集，不引入额外 lookup；只在 finalize 时补很少的行（常见是几十/几百行，而非事实行级别）。
- **语义清晰**：补全仅影响“最终输出覆盖哪些 group”，不影响聚合本身。

缺点（可接受）：
- 若 output 含 `rank_fields`，补全行的 rank 默认只能是 `None`（Decision 9），因为排名已在 finalize 前完成。

### `before_aggregate`（defer）

含义：在聚合发生之前，把缺失 key 作为“空 group”注入，使其参与聚合、排名与 post field 计算。

典型需求示例：
- “员工排行榜”：按 `employee_id` 聚合后计算 `rank_by(amount_sum)`，希望零销售员工也能出现在榜单中，并且 **rank 为最后**（而不是 `None`）。

优点：
- **排名语义更自然**：补全行可以参与 rank/score_by_rank，避免 `None` rank。
- **可覆盖更多 producer/post 语义**：某些 post fields 若依赖 rank 或聚合中间态，before_aggregate 更直观。

缺点（因此 defer）：
- **语义复杂度高**：需要定义“注入的空 group 在聚合前到底是什么形态”（是注入一条 synthetic main row？还是直接注入聚合器内部的 group？）
- **执行成本可能爆炸**：若通过 synthetic main row 注入，则可能触发整条数据流（lookups/compute），从“补几行”退化为“补全量维度 × 全链路执行”。
- **与现有模型冲突更大**：main_source 作为 row universe 的假设会被弱化，且多输出场景更难解释。

结论：v1 明确不做；未来若确有强需求，建议另开 RFC，并优先考虑更窄的模式（例如 `before_rank`：只在排名/排序之前补全、但不触发 ref lookups），以控制成本与歧义。

### detail output 上的 `ensure_keys`（defer）

detail output 指不含 `aggregate` 的输出，其行数通常与 main_source 行数同阶或更大。对 detail output 做 “ensure_keys” 在语义上通常不成立：
- detail 输出可能是“一对多”（同一 key 产生多行）；补一行还是补多行没有自然定义。
- 大量非 key 字段没有合理默认值，补出来的行很可能是误导数据。

结论：v1 不支持 detail output 的 ensure_keys；需要“维度完整性”的场景，优先用 derived output（group_by 维度键）表达。

## Decisions

### Decision 1: `ensure_keys` 为 output-level（且仅 derived output 可用）

**选择：**
- 将 `ensure_keys` 配置放在 `outputs[*]`（并要求同时存在 `aggregate`），而不是放在 `main_source`。

**理由：**
- `ensure_keys` 的语义依赖 output 的 `aggregate.group_by` 与输出字段集合；放在 `main_source` 会在多输出场景产生歧义（不同 output 的 group_by/字段不同）。
- output-level 更贴近实现位置（derived outputs finalize 阶段），降低跨模块耦合。

### Decision 2: `default/default_by` 仅作用于 ref 字段，并在 LoadRef 的 miss 写回路径生效

**选择：**
- `default` / `default_by` 只允许声明在“会发生 relation lookup”的 source 字段上（即 ref 字段：显式 relation 或可推断 lookup_steps）。
- 在 LoadRef flow 的 miss 写回路径（含：外键为 None、任一步 miss、最终 miss）按字段填入缺省值；未声明缺省值的字段仍写回 `None`。

**理由：**
- 将缺省值限定在 ref miss 语义上，可以避免把 `default` 变成“任意 `None` 的 coalesce”，从而误掩盖数据质量问题（例如真实字段值为 None）。
- 实现上与当前 miss 写回集中点一致（`flow.py`），成本低且易验证。

### Decision 3: `default_by` 复用 `call_by` 语法与安全边界

**选择：**
- `default_by` 采用与 `fields.*.call_by` 一致的表达式语法：`reference(args..., kw=...)`。
- 解析与 allowlist 校验复用现有 `parse_call_by` + `SecurePythonReferenceResolver`；运行期通过 `RuntimeBindings` 注入可调用对象，避免执行期 import。

**理由：**
- 统一语法与安全边界能显著降低维护面与用户心智负担。
- 支持按行字段依赖计算缺省值（只在 miss 时触发），覆盖“缺省值依赖其它字段”的真实需求。

### Decision 4: `default_by` 依赖字段必须是 pre-ref 可用字段（否则 fail-fast）

**选择：**
- `default_by` 表达式中的字段依赖（`parse_call_by(...).field_names`）只允许引用：
  - main_source 上的 **non-ref 源字段**（无需 LoadRef）
  - **pre-ref derived** 字段（仅依赖上述字段的派生字段；现有 planner 已有同名概念）
- 若引用了 ref 字段或 post-ref derived 字段，系统 fail-fast 并输出阻塞链条（类似“派生字段参与 join key”的现有错误风格）。

**理由：**
- `default_by` 发生在 LoadRef 写回 miss 的当下，如果允许依赖尚未计算的字段，会导致“默认值隐式退化为 None”，难以诊断且不稳定。
- 复用 planner 的 pre-ref 概念，能最小化新增规则面。

### Decision 5: `default/default_by` 的结果仍会经过 `value_cast`/value transform

**选择：**
- 对 ref 字段，系统先判定 hit/miss 并得到“候选值”（extract value 或 default/default_by 值），随后仍执行该字段的 `value_cast`（以及未来可能的 value_ops）。

**理由：**
- 避免出现“hit 行经过 value_cast，但 miss 行 default 未经过 cast”导致同一字段类型不一致。
- 同时减少用户心智负担：字段的类型语义由 `value_cast` 决定，而不是由 default 的字面量类型偶然决定。

### Decision 6: `ensure_keys` 使用“维度 source 的 mapping keys”作为期望键集合，并提供 `on` 但保持无歧义

**选择：**
- `ensure_keys.from` 引用一个 `sources.<id>`（维度源），以其 loader 结果 mapping 的 keys 作为期望键集合。
- `ensure_keys.on` 为可选字段：缺省等于 `aggregate.group_by`；若显式提供，则必须与 `aggregate.group_by` 完全一致（v1 不支持不同名映射/子集映射）。

**理由：**
- 与现有 lookup 模型一致：source 的“可 lookup 的键空间”就是 mapping keys。
- `on` 的主要价值是“自解释 + 未来扩展位”；但 v1 必须避免在多输出或复合键场景引入新歧义。

### Decision 7: `ensure_keys` 的 key 对齐使用 derived outputs 的 key_normalization 口径

**选择：**
- ensure_keys 在比较“期望键集合”与“已产出键集合”时，必须使用与 derived outputs 相同的 key_normalization 规则（`raw` vs `auto_str` 等），以降低类型不一致导致的误补全。

**理由：**
- derived outputs 已对 group key 提供确定的 key_normalization 口径；ensure_keys 必须与其一致，否则即使“逻辑相等”的 key 也会被当作不同从而补出重复/错误行。

### Decision 8: 补全行的 identity 推导覆盖常见聚合 producer；其余字段默认为 None，可被 defaults 覆盖

**选择：**
- 对 `count/count_true/count_distinct/sum` 推导 `0`；对 `min/max` 推导 `None`；对 rank/post 字段推导 `None`。
- 允许 `ensure_keys.defaults` 显式覆盖任意输出字段（包括 post 字段）。

**理由：**
- 该集合覆盖绝大多数“零填充”报表场景且实现成本低。
- 对 rank/post 默认 None 可避免补全行参与排名/二次派生产生语义争议。

### Decision 9: ensure_keys 的输出顺序策略需要明确“是否存在 rank_fields”

**选择：**
- 当 derived output **不包含** `rank_fields` 时：输出通常已经按 group_by 稳定排序；ensure_keys 应将缺失 keys **插入到稳定排序位置**（merge 两个有序 key 列表），保持整体维度顺序直观。
- 当 derived output **包含** `rank_fields` 时：输出顺序不再是纯 group_by 排序；ensure_keys 不应打乱原有排序，而是将补全行按确定性顺序追加在末尾，并在 diagnostics 中记录提示（rank 场景下“补全行 rank 为 None”）。

**理由：**
- 这是最小惊讶原则：不改变用户显式引入的排序/排名语义，同时仍满足“维度完整性”。

### Decision 10: 文档/生成边界与 drift gate

**选择：**
- schema 变更只改 `src/scalim/dsl/yaml_dsl/schema_dsl/models/**`（SSOT）与严格 validator；`src/scalim/dsl/yaml_dsl/schema/demand.gen.json` 仅通过 `just gen-yaml-dsl-schema` 刷新。
- OpenSpec 规格变更通过本 change 的 `specs/**` 表达；落地后由 archive/sync 流程更新 `openspec/specs/**`。

### Decision 11: `default_by` 提供内置 `^defaults/*` vocabulary（最小集合）

**选择：**
- 系统 MUST 提供 `^defaults/` 命名空间 builtin callables，可被 `default_by` 引用且不需要 allowlist。
- v1 最小集合（可扩展，但先从最小面出发）：
  - `^defaults/null`: 恒返回 `None`
  - `^defaults/zero_of_value_cast`: 按字段 `value_cast` 推导“零/空”缺省值（int→0，decimal→Decimal(0)，str→""，bool→False，其它→None）
- 这些 builtin 的返回值仍会遵循 Decision 5：最终写回前会经过字段的 `value_cast`/value transform。

**理由：**
- 覆盖最常见的“补 0/补空串”场景，且与字段类型语义一致，避免业务侧重复写字面量/自建函数。
- 将常用策略作为稳定 vocabulary，降低维护与沟通成本（实现者只需支持小集合即可交付高收益）。

### Decision 12: `ensure_keys` 必须复用 `preload_forever` cache（避免维度源重复加载）

**选择：**
- **WHEN** `ensure_keys.from` 指向的 source 启用了 `cache_mode: preload_forever`（或等价的全局预加载缓存）
  - **THEN** ensure_keys MUST 从 PreloadCache 读取该 source 的 mapping/keys，且 MUST NOT 触发第二次 loader 调用。
- **WHEN** 未启用 preload cache
  - **THEN** ensure_keys MAY 在运行期加载维度源一次，并 SHOULD 在同一 run 内按 `source_id` memoize keys（避免多 output 重复 IO）。

**理由：**
- 键空间补全通常依赖全量维度 roster；重复加载会直接变成可观测性能回归，也会放大外部数据源的负载。

## Risks / Trade-offs

- [default 可能掩盖数据质量问题] → 限定仅对 ref miss 生效；并建议在 guardrails/required_fields 场景下对关键字段继续 fail-fast。
- [ensure_keys 依赖维度键空间的一致性]（key_normalization/lookup_cast/value_cast 不一致可能导致“补全行与实际 group 不可对齐”） → 编译期给出诊断提示；文档明确推荐对齐 key space。
- [维度源非 preload_forever 时可能产生额外 IO] → 编译期提示推荐 `cache_mode: preload_forever`；运行期在 preload_forever 场景 MUST 复用 PreloadCache；未启用 preload 时仍需一次性加载维度键集合并按 run memoize。
- [多输出场景的复用需求] → 先做 output-level，后续如有强需求再加 demand-level sugar（不改变语义）。

## Implementation Outline (for Handoff)

本节给出面向实现者的落点清单（**改哪里**、**怎么连起来**、**怎么验证**），避免依赖口口相传。

### YAML Authoring Surface (v1)

1) Source 字段缺省值：
- `main_source.fields.<fid>.default` / `default_by`
- `sources.<sid>.fields.<fid>.default` / `default_by`
- 互斥；仅允许在 ref 字段上声明（否则校验失败）

2) Derived output 补全键空间：
- `outputs[*].ensure_keys`（要求同一 output 声明 `aggregate`）
- 建议形态：
  - `from: <source_id>`
  - `on: <group_by list>`（可省略；缺省等于 group_by）
  - `defaults: {<out_field_id>: <literal>, ...}`（可选）

### Schema SSOT & Generated Schema

- SSOT：
  - `src/scalim/dsl/yaml_dsl/schema_dsl/models/field.py`（`SourceFieldConfig` 新字段）
  - `src/scalim/dsl/yaml_dsl/schema_dsl/models/outputs.py`（`OutputTargetConfig` 新字段/子模型）
- 生成物（禁止手改）：`src/scalim/dsl/yaml_dsl/schema/demand.gen.json`
- 验证入口：`just gen-yaml-dsl-schema` + 现有 drift gate tests

### Strict Validation & Parsing

- 解析：
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/fields.py` 需要把 `default/default_by` 解析进 `SourceFieldConfig`
  - `ensure_keys` 建议走 outputs parser/validator（与 aggregate 同处），避免在 main_source 阶段引入多输出歧义
- 校验（fail-fast）：
  - `default` 与 `default_by` 互斥
  - `default/default_by` 只能出现在 ref 字段（必须能解析 relation/lookup_steps）
  - `ensure_keys` 只能用于 aggregate output；`from` 必须引用存在的 source；`on` 若存在必须等于 `aggregate.group_by`

### IR & Runtime Linking (Field Defaults)

- IR 建议：
  - `FieldIr` 增加 `default` 相关字段（literal + optional call_by spec + deps）
  - 运行期将 `default_by` 解析为 `CallBySpecIr`（复用 call_by parser 与 resolver）
- runtime linking：
  - 为每个声明了 `default_by` 的字段生成并注册一个 “default calculator”（函数对象由 resolver 解析；ctx 结构复用 `ComputeCallContextIr`）
  - 解析/签名预检查必须复用 allowlist 与 call_by preflight 语义

### Execution: Apply defaults on miss (LoadRef)

- 修改点：`src/scalim/execution/executor/operators/load_ref/flow.py::_write_final_step_row`
  - 当 lookup miss 时，不再无条件写回 None；而是按字段 default/default_by 计算候选值并写回
  - 候选值写回前仍需经过该字段的 `value_transform`（value_cast）

### Execution: ensure_keys for derived outputs

实现建议：在 output composition 装配阶段对 aggregator 做 wrapper，而不是改动 GroupByAggregator/RankedGroupByAggregator 内核。

- 在 `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py`：
  - 解析/编译 `outputs[*].ensure_keys` 并挂载到 derived target spec（需要为 derived target spec 增加字段）
  - 维度源 loader 的解析使用 `SecurePythonReferenceResolver`，并遵循 allowlist（与现有 aggregate call_by 一致）
- 在 `src/scalim/execution/output_composition.py`：
  - 当 target 存在 ensure_keys 配置时，用 `EnsureKeysAggregator` 包装 `t.derived.build_aggregator(...)` 返回的 aggregator
  - wrapper 的 `finalize_rows()`：
    - 调用下游 finalize_rows 得到 base rows
    - 调用“维度 keys provider”得到 expected keys（Decision 12：优先复用 PreloadCache；否则加载一次并 memoize）
    - 计算 missing keys 并构造补全行（按 defaults/identity 推导/None）
    - 依据 Decision 9 处理顺序（无 rank_fields: merge 插入；有 rank_fields: 追加）
  - wrapper 的 `diagnostics()`：
    - 在 meta 中记录 `expected_count/produced_count/filled_count/filled_ratio`
    - 当 filled_ratio 过高或 expected_count=0 时写入 audit_events

### Testing Strategy (verifiable)

- 严格校验单测（validator）：
  - default/default_by 互斥
  - 非 ref 字段拒绝 default/default_by
  - ensure_keys 引用不存在 source 报错
- 执行链路测试（execution）：
  - hit 行不被 default 覆盖；miss 行按 default/default_by 输出
  - fk None / multi-step miss 的覆盖
  - ensure_keys 单键/复合键补全 + diagnostics meta 输出稳定

## Migration Plan

- additive：旧 YAML 不变；仅在声明新字段时生效。
- 回滚：移除 YAML 中的新字段即可回到旧行为（不需要数据迁移）。

## Open Questions (explicitly deferred)

- ensure_keys 是否需要支持 “before_aggregate” 或 detail output？
  - 见上文 Clarifications：这些能力语义与成本都显著更高；v1 以 after_aggregate/derived-only 交付最大性价比。
