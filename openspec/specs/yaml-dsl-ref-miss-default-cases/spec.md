# yaml-dsl-ref-miss-default-cases Specification

## Purpose
TBD - created by archiving change c0-yaml-dsl-ref-miss-default-cases. Update Purpose after archive.
## Requirements
### Requirement: YAML ref fields MAY declare ordered default cases for relation miss

系统 MUST 支持在 source ref 字段上声明 `default` ordered cases:

- `default` MUST 为数组（按声明顺序 first-match）
- 每个 case MUST 包含 `when`
- v1 中 `when` MUST 仅允许 `relation_miss`
- 每个 case MUST 在 `literal` 与 `call_by` 之间二选一（oneOf）
  - `literal` MUST 为 YAML 标量（`int|float|str|bool|null`）
  - `call_by` MUST 为字符串，并且 MUST 显式包含 `()` 以表示“可调用表达式”（例如 `^defaults/zero_of_value_cast()`）

`default` MUST 仅允许出现在带 `relation:` 的 source field 上；若字段未声明 `relation`，系统 MUST 在校验阶段 fail-fast。

#### Scenario: ref field default literal is accepted
- **WHEN** 用户在一个带 `relation` 的字段上声明：
  ```yaml
  sources:
    create_metrics:
      fields:
        create_order_count:
          relation: paid_to_create
          value_cast: int
          default:
            - when: relation_miss
              literal: 0
  ```
- **THEN** schema/strict validation MUST 通过

#### Scenario: default on non-ref field is rejected
- **WHEN** 用户在一个未声明 `relation` 的字段上声明 `default`
- **THEN** 系统 MUST 在校验阶段 fail-fast 并指向该字段路径

#### Scenario: default case oneOf is enforced
- **WHEN** 某个 default case 同时声明 `literal` 与 `call_by`
- **THEN** 系统 MUST 在校验阶段 fail-fast

#### Scenario: call_by requires explicit parentheses
- **WHEN** 某个 default case 声明 `call_by: ^defaults/zero_of_value_cast`（不包含 `()`）
- **THEN** 系统 MUST 在校验阶段 fail-fast

### Requirement: default cases MUST only apply on relation miss and are first-match

系统 MUST 将 default case 视为 “relation miss 的替代值”：

- 当 relation lookup **命中** 时，系统 MUST 返回命中行的字段值（即使该字段值为 `None`），且 MUST NOT 应用 default
- 当 relation lookup **未命中** 且字段声明了 `default` 时，系统 MUST 以 first-match 规则选择第一个满足 `when` 的 case 并生成替代值
- 当 relation lookup **未命中** 且字段未声明 `default` 时，系统 MUST 返回 `None`（保持既有行为）

#### Scenario: relation miss uses default literal
- **GIVEN** 某 ref 字段声明了 `default: [{when: relation_miss, literal: 0}]`
- **WHEN** relation lookup miss（例如 key 不存在）
- **THEN** 该字段写回值 MUST 为 `0`

#### Scenario: relation hit does not apply default even if value is None
- **GIVEN** relation lookup 命中一行，但该行的目标字段值为 `None`
- **WHEN** ref 写回发生
- **THEN** 该字段写回值 MUST 保持为 `None`

### Requirement: selected default value MUST go through value_cast before writeback

系统 MUST 在写回 ref 字段前统一执行 `value_cast`：

- 命中值与 default 替代值均 MUST 进入同一条 `value_cast` 转换路径
- 若转换失败，系统 MUST 按既有 guardrails/错误边界处理（不在本规格中重新定义）

#### Scenario: default literal is cast using value_cast
- **GIVEN** 某字段声明 `value_cast: int`
- **AND** default case 声明 `literal: \"0\"`
- **WHEN** relation miss
- **THEN** 写回值 MUST 为整数 `0`

### Requirement: default call_by MUST only depend on pre-ref available fields (compile-time fail-fast)

系统 MUST 对 `default[*].call_by` 执行依赖字段静态分析，并在编译/校验阶段 fail-fast 拒绝“依赖尚未就绪字段”的配置。

#### Definition: pre-ref available fields

pre-ref 可用字段 MUST 满足以下条件之一：

- main_source 的非 ref 字段（即：source field 且未声明 `relation`）
- derived 字段，且其依赖闭包中不包含任何 ref 字段（source field 声明了 `relation`）或依赖 ref 的 derived 字段

#### Scenario: default call_by may reference main_source non-ref fields
- **WHEN** 某 ref 字段 default case 声明：
  ```yaml
  main_source:
    fields:
      group_name: {extract: group_name}
  sources:
    create_metrics:
      fields:
        create_order_count:
          relation: paid_to_create
          value_cast: int
          default:
            - when: relation_miss
              call_by: myapp.defaults:zero_by_group(group=group_name)
  ```
- **THEN** 编译/校验 MUST 通过（因为 `group_name` 为 pre-ref 可用字段）

#### Scenario: default call_by that depends on a ref field is rejected
- **WHEN** 某 ref 字段 default case 的 `call_by` 参数依赖另一个 ref 字段（例如 `dept_name` 也需要 relation 才能得到）
- **THEN** 系统 MUST 在编译/校验阶段 fail-fast
- **AND** 错误 MUST 可定位到该 `default[*].call_by` 的字段路径

### Requirement: builtin `^defaults/zero_of_value_cast()` MUST be available for default call_by

系统 MUST 在 builtin callable vocabulary 中提供 `^defaults/zero_of_value_cast()`，其行为 MUST 由字段 `value_cast` 决定：

- `int` → `0`
- `str` → `\"\"`
- `bool` → `False`
- 其他 cast → `None`（或由 cast 规则决定的“零值”）

#### Scenario: builtin zero_of_value_cast returns 0 for int fields
- **GIVEN** 某 ref 字段声明 `value_cast: int`
- **AND** default case 声明 `call_by: ^defaults/zero_of_value_cast()`
- **WHEN** relation miss
- **THEN** 写回值 MUST 为 `0`

