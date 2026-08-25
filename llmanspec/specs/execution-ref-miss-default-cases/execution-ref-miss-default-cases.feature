# language: zh-CN
# capability: execution-ref-miss-default-cases
# purpose: 定义 YAML DSL 中 source ref 字段的 relation miss 默认值机制。允许用户在关联查询未命中时使用有序的默认值替代 None，提高配置表达能力和错误容错性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: execution-ref-miss-default-cases

  @req:r43 @human
  场景: YAML ref fields MAY declare ordered default cases for relation miss
    - 系统 MUST 支持在 source ref 字段上声明 `default` ordered cases： - `default` MUST 为数组（按声明顺序 first-match） - 每个 case MUST 包含 `when`（v1 中 MUST 仅允许 `relation_miss`） - 每个 case MUST 在 `literal` 与 `call_by` 之间二选一（oneOf） - `literal` MUST 为 YAML 标量 - `call_by` MUST 为字符串且显式包含 `()` 以表示可调用表达式 `default` MUST 仅允许出现在带 `relation:` 的 source field 上；若字段未声明 `relation`，系统 MUST 在校验阶段 fail-fast。

  @req:r287 @human
  场景: default cases MUST only apply on relation miss and are first-match
    - 系统 MUST 将 default case 视为 “relation miss 的替代值”： - 当 relation lookup **命中** 时，系统 MUST 返回命中行的字段值（即使该字段值为 `None`），且 MUST NOT 应用 default - 当 relation lookup **未命中** 且字段声明了 `default` 时，系统 MUST 以 first-match 规则选择第一个满足 `when` 的 case 并生成替代值 - 当 relation lookup **未命中** 且字段未声明 `default` 时，系统 MUST 返回 `None`（保持既有行为）

  @req:r411 @human
  场景: selected default value MUST go through value_cast before writeback
    - 系统 MUST 在写回 ref 字段前统一执行 `value_cast`： - 命中值与 default 替代值均 MUST 进入同一条 `value_cast` 转换路径 - 若转换失败，系统 MUST 按既有 guardrails/错误边界处理（不在本规格中重新定义）

  @req:r506 @human
  场景: default call_by MUST only depend on pre-ref available fields (compile-time fail-
    - 系统 MUST 对 `default[*].call_by` 执行依赖字段静态分析，并在编译/校验阶段 fail-fast 拒绝”依赖尚未就绪字段”的配置。 pre-ref 可用字段 MUST 满足以下条件之一： - main_source 的非 ref 字段 - derived 字段，且其依赖闭包中不包含任何 ref 字段或依赖 ref 的 derived 字段

  @req:r583 @human
  场景: builtin `^defaults/default()` MUST be available for default call_by
    - 系统 MUST 在 builtin callable vocabulary 中提供 `^defaults/default()`（别名 `^defaults/default_of_value_cast()`），其行为 MUST 由字段 `value_cast` 决定： - `int` → `0` - `str` → `\"\"` - `decimal` → `0` - `auto` → `\"\"` 该 builtin MUST 要求字段显式声明 `value_cast`；若缺失，系统 MUST 在编译/校验阶段 fail-fast。
  @req:r43 @human
  场景: ref-field-default-literal-is-accepted
    - 必须成立：当 用户在一个带 `relation` 的字段上声明 `default: [{when: relation_miss, literal: 0}]`；那么 schema/strict validation MUST 通过
    当 用户在一个带 `relation` 的字段上声明 `default: [{when: relation_miss, literal: 0}]`
    那么 schema/strict validation MUST 通过

  @req:r43 @human
  场景: default-on-non-ref-field-is-rejected
    - 必须成立：当 用户在一个未声明 `relation` 的字段上声明 `default`；那么 系统 MUST 在校验阶段 fail-fast 并指向该字段路径
    当 用户在一个未声明 `relation` 的字段上声明 `default`
    那么 系统 MUST 在校验阶段 fail-fast 并指向该字段路径

  @req:r43 @human
  场景: default-case-oneof-is-enforced
    - 必须成立：当 某个 default case 同时声明 `literal` 与 `call_by`；那么 系统 MUST 在校验阶段 fail-fast
    当 某个 default case 同时声明 `literal` 与 `call_by`
    那么 系统 MUST 在校验阶段 fail-fast

  @req:r43 @human
  场景: call-by-requires-explicit-parentheses
    - 必须成立：当 某个 default case 声明 `call_by: ^defaults/default`（不包含 `()`）；那么 系统 MUST 在校验阶段 fail-fast
    当 某个 default case 声明 `call_by: ^defaults/default`（不包含 `()`）
    那么 系统 MUST 在校验阶段 fail-fast
  @req:r287 @human
  场景: relation-miss-uses-default-literal
    - 必须成立：假如 某 ref 字段声明了 `default: [{when: relation_miss, literal: 0}]`；当 relation lookup miss（例如 key 不存在）；那么 该字段写回值 MUST 为 `0`
    假如 某 ref 字段声明了 `default: [{when: relation_miss, literal: 0}]`
    当 relation lookup miss（例如 key 不存在）
    那么 该字段写回值 MUST 为 `0`

  @req:r287 @human
  场景: relation-hit-does-not-apply-default-even-if-value-is-none
    - 必须成立：假如 relation lookup 命中一行，但该行的目标字段值为 `None`；当 ref 写回发生；那么 该字段写回值 MUST 保持为 `None`
    假如 relation lookup 命中一行，但该行的目标字段值为 `None`
    当 ref 写回发生
    那么 该字段写回值 MUST 保持为 `None`
  @req:r411 @human
  场景: default-literal-is-cast-using-value-cast
    - 必须成立：假如 某字段声明 `value_cast: int`；当 relation miss；那么 写回值 MUST 为整数 `0`
    假如 某字段声明 `value_cast: int`
    当 relation miss
    那么 写回值 MUST 为整数 `0`
  @req:r506 @human
  场景: default-call-by-may-reference-main-source-non-ref-fields
    - 必须成立：假如 main_source 包含非 ref 字段 `group_name`；当 某 ref 字段 default case 声明 `call_by: myapp.defaults:zero_by_group(group=group_name)`；那么 编译/校验 MUST 通过（因为 `group_name` 为 pre-ref 可用字段）
    假如 main_source 包含非 ref 字段 `group_name`
    当 某 ref 字段 default case 声明 `call_by: myapp.defaults:zero_by_group(group=group_name)`
    那么 编译/校验 MUST 通过（因为 `group_name` 为 pre-ref 可用字段）

  @req:r506 @human
  场景: default-call-by-that-depends-on-a-ref-field-is-rejected
    - 必须成立：当 某 ref 字段 default case 的 `call_by` 参数依赖另一个 ref 字段（例如 `dept_name` 也需要 relation 才能得到）；那么 系统 MUST 在编译/校验阶段 fail-fast
    当 某 ref 字段 default case 的 `call_by` 参数依赖另一个 ref 字段（例如 `dept_name` 也需要 relation 才能得到）
    那么 系统 MUST 在编译/校验阶段 fail-fast
  @req:r583 @human
  场景: builtin-default-returns-0-for-int-fields
    - 必须成立：假如 某 ref 字段声明 `value_cast: int`；当 relation miss；那么 写回值 MUST 为 `0`
    假如 某 ref 字段声明 `value_cast: int`
    当 relation miss
    那么 写回值 MUST 为 `0`
