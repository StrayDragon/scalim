## Context

`sources.*.normalize.kind=index_by_key` 目前在运行时校验与 YAML→IR conversion 中要求显式填写 `normalize.key_field`,并且该字段还必须等于 `sources.<id>.key`。
这导致 `key` 与 `key_field` 在大多数场景下重复出现,造成 YAML 噪音与误配风险。

此外,现有 YAML JSON Schema 层面 `key_field` 不是 required,而运行时又把它当作 required,使编辑器/Schema 与真实校验行为不一致。

本 change 的范围是:仅对 `index_by_key` 放宽 `key_field` 为可选字段(默认推导),并保证 validator 与 conversion 对缺省逻辑完全一致。

## Goals / Non-Goals

**Goals:**

- 允许在 `normalize.kind=index_by_key` 时省略 `normalize.key_field`,并将其默认推导为 `sources.<id>.key`（仅当 `key` 为单字段字符串时）。
- 允许用户显式填写 `normalize.key_field` 以提升可读性,但仍强约束其与 `sources.<id>.key` 一致,避免语义漂移。
- 保持 `normalize.kind=index_by_key` 对 composite key 的拒绝策略不变（仍 fail-fast）。
- 保持其它 normalize kind 的行为不变（`key_field` 只对 `index_by_key` 有意义,其它 kind 出现该字段仍应被拒绝）。

**Non-Goals:**

- 不引入 “`key` 与 `key_field` 可不一致” 的新语义（这会改变 relation/lookup contract,属于更大范围的提案）。
- 不在本 change 内支持 composite key 的 `index_by_key`（这需要新的 IR 与 lookup/field extraction contract）。
- 不重构 normalize 的整体 pipeline 与扩展点（例如 `normalize.call_by`）。

## Decisions

### 1) 在 validator 与 conversion 中一致计算 effective `key_field`

允许省略 `key_field` 后,如果只放宽 validator 而 conversion 仍将其视为必填,会造成 “validate 通过但 runtime 编译失败” 的体验问题。
因此该 change 以 “effective key_field” 为核心决策:两处都按同一规则计算:

- 若 `normalize.key_field` 为非空字符串:使用该值,并校验其等于 `sources.<id>.key`
- 若 `normalize.key_field` 缺失或为空字符串:默认取 `sources.<id>.key`

并且 conversion MUST 将计算后的 effective `key_field` 写入 IR,使后续执行层不需要处理 `None` 分支。

### 2) 保持显式 `key_field` 与 `key` 的强一致性约束

虽然允许省略 `key_field`,但仍保留 “显式填写时必须与 `key` 一致” 的 fail-fast 约束。
这样可以同时满足:

- YAML 面积收敛（省略是常用路径）
- 可读性诉求（显式填写仍合法）
- 避免 “用户以为这两者是两套语义” 的漂移风险

### 3) composite key 仍一律拒绝

当 `sources.<id>.key` 为 tuple/list 等复合键时,`normalize.kind=index_by_key` 仍必须被拒绝。
该 change 只减少冗余字段,不改变 `index_by_key` 的形状与 contract。

### 4) 在 Schema/hover 文案中显式强调缺省行为

为了降低 `key_field` 省略后的理解成本,需要在 YAML JSON Schema / editor hover 文案中明确:
当 `normalize.kind=index_by_key` 且 `key_field` 省略/为空时,其 effective 值默认取 `sources.<id>.key`（仅单字段 key）。
这可以把 “默认推导” 从隐式行为变成可发现的用户契约,减少使用方困惑。

## Risks / Trade-offs

- `[隐式默认导致阅读不显式]` → 允许用户保留显式 `key_field` 作为自注释；同时在 docs/demo YAML 中给出省略写法示例。
- `[validator 与 conversion 再次出现分歧]` → 为 “省略/显式/误配/复合键” 四类路径补齐测试,以测试作为一致性 gate。
- `[错误信息不清晰]` → 在校验失败时分别给出 “composite key 不支持” 与 “key_field 与 key 不一致” 的明确提示,避免把配置问题误诊为运行时数据问题。

## Migration Plan

- 对现有 YAML 完全向后兼容:显式填写 `normalize.key_field` 的配置不需要修改。
- 在仓库内示例 YAML 中,可以在实现完成后逐步移除重复的 `key_field` 以验证缺省行为（不涉及 `.gen.` 生成物手改）。

## Open Questions

无。
