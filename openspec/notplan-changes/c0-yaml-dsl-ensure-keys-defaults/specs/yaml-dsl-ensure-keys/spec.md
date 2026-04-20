# yaml-dsl-ensure-keys (Delta Spec)

## ADDED Requirements

### Requirement: Derived outputs MAY declare `ensure_keys` to fill missing aggregate groups
系统 SHALL 在 YAML `outputs[*]` 层提供可选配置 `ensure_keys`，用于对 **声明了 `aggregate` 的 output** 在 finalize 阶段补全缺失的 group-by 键空间。

配置约束：
- `outputs[*].ensure_keys` MUST 仅在同一 output 声明了 `aggregate` 时可用
- `ensure_keys.from` MUST 引用 `sources.<source_id>` 中已声明的 source
- `ensure_keys.on` MAY 省略；省略时系统 MUST 视其等于 `outputs[*].aggregate.group_by`
- **WHEN** `ensure_keys.on` 显式提供
  - **THEN** `ensure_keys.on` MUST 与 `outputs[*].aggregate.group_by` 等价（单键为字符串；复合键为字符串数组，且顺序一致）

补全语义：
- 系统 MUST 将 `ensure_keys.from` 的 loader 结果视为 mapping，并将 mapping keys 作为“期望键集合”
- 系统 MUST 将聚合输出行的 `group_by` 字段值组成的 key tuple 作为“已产出键集合”
- 对 `期望键集合 - 已产出键集合` 中的每个 key，系统 MUST 追加一行“补全行”

#### Scenario: missing groups are appended
- **GIVEN** `aggregate.group_by=[employee_id]`
- **AND** `ensure_keys.from=employees` 且 employees mapping keys 为 `{1,2,3}`
- **WHEN** 聚合结果仅包含 employee_id `{1,3}`
- **THEN** 输出结果 MUST 额外包含 employee_id 为 `2` 的补全行

### Requirement: Filled rows MUST apply field defaults with deterministic identity inference
系统 MUST 按以下优先级为补全行填充字段值：
1) `ensure_keys.defaults.<out_field_id>`（显式覆盖）
2) 基于聚合 producer 的 identity 推导（仅对聚合指标字段）
3) `None`

identity 推导 MUST 至少覆盖：
- `count` / `count_true` / `count_true_gte` / `count_distinct` → `0`
- `sum` → `0`
- `min` / `max` → `None`
- rank 字段与聚合后派生字段（post fields）→ `None`

并且：
- `group_by` 字段 MUST 从补全 key 写入（单键直接写入；复合键按 `ensure_keys.on` 顺序拆分写入）
- 若 `ensure_keys.defaults` 覆盖了某个聚合指标字段，则 MUST 覆盖 identity 推导值

#### Scenario: defaults override inferred identity
- **GIVEN** 某聚合指标 `sum_sales` 的 producer 为 `sum`
- **AND** `ensure_keys.defaults.sum_sales=999`
- **WHEN** 某个 key 需要补全行
- **THEN** 该补全行的 `sum_sales` MUST 为 `999`（而非推导的 `0`）

### Requirement: ensure_keys MUST compare keys using derived-output key_normalization semantics
系统 MUST 使用与派生聚合一致的 key_normalization 口径对齐 key 空间，避免类型不一致导致误补全：

- **WHEN** derived output 的 key_normalization 为 `raw`
  - **THEN** ensure_keys MUST 使用原始 key 值进行对齐比较
- **WHEN** derived output 的 key_normalization 非 `raw`（例如 `auto_str`）
  - **THEN** ensure_keys MUST 按同一规则规范化“期望键集合”与“已产出键集合”后再比较

#### Scenario: key_normalization aligns string/int keys
- **GIVEN** derived output key_normalization 为非 raw（例如 `auto_str`）
- **AND** 期望键集合包含 `1`（int）
- **AND** 已产出键集合包含 `"1"`（str）
- **WHEN** 执行 ensure_keys
- **THEN** 系统 MUST 将两者视为同一 key（不得补出重复行）

### Requirement: ensure_keys MUST preserve deterministic output ordering
系统 MUST 保证补全后的聚合输出顺序确定性，并明确 rank 场景的顺序策略：

- **WHEN** 该 output 未声明任何 rank 字段（纯 group_by + metrics/可选 post fields）
  - **THEN** 补全后的整体结果 MUST 按 group_by 的稳定排序规则输出（缺失 key 插入到正确位置）
- **WHEN** 该 output 声明了 rank 字段
  - **THEN** 系统 MUST 保持原有聚合结果的顺序不变
  - **AND** 补全行 MUST 以确定性顺序追加在末尾
  - **AND** 补全行的 rank 字段值 MUST 为 `None`（除非用户通过 `ensure_keys.defaults` 覆盖）

#### Scenario: ensure_keys output order is stable
- **WHEN** 同一份输入在多次运行中生成聚合输出且启用 ensure_keys
- **THEN** 输出行顺序 MUST 稳定一致（可对拍）

### Requirement: ensure_keys MUST reuse `preload_forever` cache for dimension keys when available
键空间补全常用维度 roster（全量 keys），因此系统 MUST 避免对同一维度源重复加载。

- **GIVEN** `ensure_keys.from` 指向的维度 source 配置了 `cache_mode: preload_forever`
- **WHEN** 同一 run 中该 source 已通过 preload cache 加载过（例如既用于 lookup，又用于 ensure_keys）
- **THEN** ensure_keys MUST 复用 preload cache 中的 mapping/keys
- **AND** MUST NOT 为 ensure_keys 再触发一次 loader IO（避免重复加载）

#### Scenario: preload cache prevents double-load
- **GIVEN** `employees` source 为 `cache_mode: preload_forever`
- **AND** 某 output 配置 `ensure_keys.from: employees`
- **WHEN** 该 run 中 `employees` 既参与 relation lookup，又参与 ensure_keys
- **THEN** `employees` 的 loader MUST 仅被调用一次（可通过计数型 loader 测试验证）
