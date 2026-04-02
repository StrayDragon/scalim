## Why

我们已经对 YAML DSL 配置做过一轮瘦身，但从真实下游写法来看，当前 authoring surface 仍存在两类问题:

1) **高频噪音**：大量重复/样板化写法让 YAML 变胖、diff 变嘈杂、review 成本上升。
2) **边界不清**：少数配置项更像“运行期策略/安全策略”，不应该属于 YAML mainline 的需求本体；它们一旦被复制粘贴，会在下游形成难以治理的“配置惯性”。

本提案目标不是“扩能力”，而是系统性罗列现有语法与可简化/可移除点，给出推荐的收敛路径(可拆分为多个小 change 转正)。

> 下游观察(代表性 repo 采样): `$keys` 出现频率远高于其它特性；`lookup_cast` 也非常高频；`normalize` 目前几乎只用 `index_by_key`，
> 且 `key_field` 与 `key` 100% 冗余重复。这些都是“减噪优先”的一等候选。

## Current Surface (Code-Backed Inventory)

### 1) `params` 模板与指令节点

当前 `params` 模板在编译期由 `src/scalim/dsl/by_yaml/params_template.py` 解析，核心语义:

- `{$init_var: <name>}`：编译期注入 init_vars 的值
- `{$keys: {as: set|list}}`：运行期注入 lookup keys
  - 也允许 `{$keys: null}`，默认 `as: set`
- `{$rows: {cache_mode: batch|none}}`：运行期注入 batch rows
  - 也允许 `{$rows: null}`，默认 `cache_mode: batch`
- 指令节点必须是**单键 mapping**，并且 `$keys` 与 `$rows` 互斥(同一模板内不可同时出现)

### 2) `lookup_cast`(source 级 / relation step 级)

当前 `lookup_cast` 语法为对象形态:

```yaml
lookup_cast:
  name: auto|int|str|sep_first
  sep: ","  # 仅 sep_first 需要
```

代码入口:
- parser: `src/scalim/dsl/by_yaml/_internal/config_parsing/parsers/sources.py` / `parsers/relations.py`
- validator: `src/scalim/dsl/by_yaml/_internal/config_parsing/validators/sources.py` / `validators/relations.py`

### 3) `sources.*.normalize`

当前 normalize 支持:
- `index_by_key` / `take_first` / `project_fields` / `map_values` / `call_by`

关键点:
- `index_by_key` 当前要求显式 `key_field`，并且必须等于 `sources.<id>.key`(强冗余约束)
- 其它 kind 的校验与 conversion 逻辑都已存在且测试覆盖较完整(移除需额外讨论与迁移策略)

### 4) “更像策略”的顶层开关

当前仍在 YAML mainline 中的两个代表:
- `include_full_error_message`：是否输出完整错误信息(可能包含敏感信息)
- `validate_unique_field_names`：是否启用“有效展示名唯一性”预检查(对某些输出表头策略生效)

对照: `guardrails` / `batch_size` / `retry` / `failure_policy` 已经迁出 YAML mainline，形成了清晰的 runtime policy boundary。

## Candidate Simplifications / Removals

### A) `$keys` / `$rows` 短写(高收益、低风险)

#### Problem

下游高频写法是:

```yaml
order_id_set: {$keys: {as: set}}
ids: {$keys: {as: list}}
rows: {$rows: {cache_mode: batch}}
```

其中 `{as: set}` 与 `{cache_mode: batch}` 在绝大多数场景等价“默认值”，但仍被迫反复写出。

#### Proposal

在保持现有写法可用的前提下，新增更短写法:

- `{$keys: list}` 等价 `{$keys: {as: list}}`
- `{$keys: set}` 等价 `{$keys: {as: set}}`
- `{$rows: none}` 等价 `{$rows: {cache_mode: none}}`
- `{$rows: batch}` 等价 `{$rows: {cache_mode: batch}}`

并且在文档/示例中将默认写法统一升级为:
- `{$keys: null}` / `{$rows: null}` 或上述字符串短写(视可读性)

> 备注: 目前实现已支持 `{$keys: null}` / `{$rows: null}`(默认 set/batch)。本提案是把“短写”做成更直觉的 authoring surface。

#### Recommendation

优先推进；这是最能立刻降低 YAML 噪音的改动，并且不会改变运行期语义。

---

### B) `lookup_cast` 短写(高收益、低风险)

#### Problem

`lookup_cast: {name: int}` 是高频样板化写法；尤其在 relation steps 中会大量重复。

#### Proposal

新增 scalar 短写:

- `lookup_cast: int|str|auto` 等价 `lookup_cast: {name: int|str|auto}`
- `sep_first` 保持对象形态(因为需要 `sep`)

并升级示例/文档为短写优先。

#### Recommendation

优先推进；对下游 YAML 体积与可读性改善明显。

---

### C) `normalize.key_field` 可选(已单独提案，建议纳入同一轮瘦身)

`index_by_key` 的 `key_field` 与 `key` 目前强冗余，已在:

- `openspec/notplan-changes/c0-yaml-source-normalize-key-field-optional/proposal.md`

单独立项。

#### Recommendation

与 A/B 同一批次推进，形成一次性“写法降噪”闭环。

---

### D) `include_full_error_message` 迁出 YAML mainline(中收益、中风险)

#### Problem

该字段更像“安全/隐私策略”，不属于需求本体；且一旦被复制粘贴到业务 YAML 中，治理成本高。

#### Proposal

参考已迁出的 runtime policy 字段(guardrails/retry 等):
- YAML 继续允许但 fail-fast 并提示迁移(或直接剥离并报错)
- 将该策略改为仅能通过 runtime entrypoints 参数配置

#### Recommendation

作为第二阶段推进；先完成 A/B/C 的 authoring 降噪，再处理策略边界迁移。

---

### E) `validate_unique_field_names` 的处置(中收益、高风险)

#### Problem

该开关在下游确实会被用来绕过“展示名冲突”预检查(例如复刻 legacy 合同/表头重复)。
贸然移除会影响下游可用性与迁移成本。

#### Options

1) **保留但收紧语义**：仅在确实会输出 `header_fields_output_by: name` 且 include_header 时才允许生效(目前已基本如此)
2) **迁出 YAML mainline**：改为 runtime 参数控制(需要给下游提供等价入口与迁移指南)
3) **完全移除**：强制要求唯一展示名；重复表头需求改用其它机制表达(例如 output/aggregate field `name` 显式允许重复)

#### Recommendation

先不动或只做语义澄清；等下游重复表头/合同复刻需求路径更清晰后再做迁出或移除决定。

## Recommended Path (Actionable Next Steps)

建议将本提案拆分为 2~3 个小 change(转正时各自有清晰边界与测试面):

1) **Authoring sugar pack**：`$keys/$rows` 短写 + `lookup_cast` 短写 + 文档/示例升级
2) **Normalize cleanup**：`index_by_key` 的 `key_field` 可选(已单独提案)
3) **Policy boundary**：`include_full_error_message` 迁出 YAML mainline（可选后续）

并以“下游代表性 YAML(ET)”+“repo demo fixtures”作为验收样本，确保:
- 写法更短、review 更快
- 语义不变
- 诊断信息仍然明确(避免 silent ignore)

