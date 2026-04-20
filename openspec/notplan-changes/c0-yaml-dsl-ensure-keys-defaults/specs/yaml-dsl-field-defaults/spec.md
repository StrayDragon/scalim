# yaml-dsl-field-defaults (Delta Spec)

## ADDED Requirements

### Requirement: Source fields MAY declare `default` / `default_by` for relation miss
系统 SHALL 允许在 source 字段配置(`main_source.fields.*` 与 `sources.*.fields.*`)中声明缺省值策略，用于处理 relation lookup miss。

语义：
- **WHEN** relation lookup 命中(hit)
  - **THEN** 字段值 MUST 为正常 lookup + extract + value_cast 结果（不得被 default 覆盖）
- **WHEN** relation lookup 未命中(miss)
  - **THEN** 若声明了 `default`，字段值 MUST 为 `default` 产生的值
  - **THEN** 若声明了 `default_by`，字段值 MUST 为 `default_by` 求值结果
  - **THEN** 若两者均未声明，字段值 MUST 为 `None`（保持现有行为）

miss 的覆盖范围 MUST 包含：
- 外键为 `None` / 无法归一化导致该行不参与 lookup
- 多 step relation 中任一步 miss
- 最终 step miss（lookup_key 不在 loader result mapping 中）

#### Scenario: `default` is applied only on miss
- **WHEN** 某字段为 ref 字段且 relation lookup miss
- **THEN** 该字段值为声明的 `default`
- **AND** 同一字段在 lookup hit 时仍输出 loader 返回值（而非 default）

### Requirement: `value_cast` MUST apply after default resolution
系统 MUST 保持字段的类型语义一致：对同一 ref 字段，无论是 lookup hit 的 extracted value，还是 miss 走 `default/default_by` 得到的值，均 MUST 经过该字段声明的 `value_cast`/value transform（若存在）。

#### Scenario: default value is casted the same as hit value
- **GIVEN** 某 ref 字段声明 `value_cast: int`
- **AND** 声明 `default: "0"`
- **WHEN** relation lookup miss
- **THEN** 最终写回的字段值 MUST 为 `0`（int）

### Requirement: `default` and `default_by` MUST be mutually exclusive and only valid on ref fields
系统 MUST 在编译/严格校验阶段对以下配置 fail-fast：
- 同一字段同时声明 `default` 与 `default_by`
- 字段未发生 relation lookup（非 ref 字段）但声明了 `default/default_by`

#### Scenario: mutually exclusive defaults are rejected
- **WHEN** 同一字段同时声明 `default` 与 `default_by`
- **THEN** 编译/校验必须失败并指出冲突配置路径

### Requirement: `default_by` MUST follow call_by security semantics and MAY reference other fields
系统 MUST 将 `default_by` 视为受控 callable 引用点，其解析与运行期执行必须遵循与 `call_by` 一致的安全边界：
- 引用解析 MUST 通过 allowlist（除非引用为 `^<id>` builtin callable）
- 参数语法 MUST 使用 `reference(args..., kw=...)` 形式并支持 `$ctx`/字段名引用
- `default_by` MUST 仅在 miss 时求值（不得对 hit 行产生额外函数调用）

并且系统 MUST 对依赖字段可用性建立清晰边界：
- `default_by` 的字段依赖 MUST 限定为 **LoadRef 之前可用** 的字段（main_source non-ref + pre-ref derived）
- 当 `default_by` 依赖 ref 字段或 post-ref derived 字段时，系统 MUST fail-fast 并给出可诊断错误

#### Scenario: `default_by` can depend on existing row fields
- **GIVEN** `default_by` 的参数引用了某个已存在字段(例如 `status=status`)
- **WHEN** relation lookup miss
- **THEN** 系统必须以该行当前字段值作为实参调用 `default_by` 并写回其返回值

#### Scenario: `default_by` referencing ref fields is rejected
- **GIVEN** 某字段 `x` 是 ref 字段（依赖 LoadRef 才能得到值）
- **WHEN** 另一个字段的 `default_by` 依赖 `x`
- **THEN** 系统 MUST 在运行前 fail-fast 并提示该依赖不是 pre-ref 可用

### Requirement: `default_by` MUST support builtin `^defaults/*` vocabulary
系统 MUST 提供一个最小内置 vocabulary，用于覆盖最常见的“缺失补 0/补空值”场景，并确保与字段 `value_cast` 语义对齐。

系统 MUST 至少提供以下 builtin callable ids（可扩展，但这些为 v1 契约）：
- `^defaults/null`：恒返回 `None`
- `^defaults/zero_of_value_cast`：按字段 `value_cast` 推导“零/空”缺省值：
  - `value_cast: int` → `0`
  - `value_cast: decimal` → `Decimal(0)`
  - `value_cast: str` → `""`
  - `value_cast: bool` → `False`
  - 其它/无法推导 → `None`（并 SHOULD 发出可诊断提示）

并且：
- builtin `^defaults/*` 引用 MUST 不需要 allowlist（仍遵循 `default_by` 的 miss-only 语义）
- **WHEN** `default_by` 引用了未知的 `^defaults/*` id
  - **THEN** 编译/严格校验 MUST fail-fast 并指出未知 builtin id

#### Scenario: builtin zero follows value_cast
- **GIVEN** 某 ref 字段声明 `value_cast: int`
- **AND** `default_by: ^defaults/zero_of_value_cast`
- **WHEN** relation lookup miss
- **THEN** 字段值 MUST 为 `0`
