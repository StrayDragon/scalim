# dense-batch-context Specification

## ADDED Requirements

### Requirement: Dense storage may be used for contiguous integer row_id batches
系统 MUST 支持在批次内 `row_id` 为连续整数的场景下使用 Dense 存储表示以降低内存占用与提高速度；实现 MAY 在满足条件时选择启用该 Dense path。

Dense path 的启用条件 MUST 可判定且可回退：
- `row_id` MUST 为 `int` 且构成连续区间（存在可计算的 `base_row_id` 与 `row_count`）。
- 条件不满足时系统 MUST 回退到通用实现，语义不变。

#### Scenario: non-contiguous row_id falls back safely
- **WHEN** 执行路径出现非连续或非整数的 `row_id`
- **THEN** 系统 MUST 回退到通用实现并保持行为一致

### Requirement: Dense and generic BatchContext are semantically equivalent
无论是否启用 Dense path，`BatchContext` 的对外语义 MUST 等价，包括但不限于：
- `set_field_value/get_field_value`
- `delete_field/delete_row_from_field/delete_row_from_all_fields`
- `disable_row`
- `get_field_keys/get_field_count/get_all_rows_for_field`

#### Scenario: set/get/delete semantics match
- **WHEN** 在同一批次内对同一字段执行 set/get 与 delete（字段删除或行级删除）
- **THEN** Dense path 与通用实现的读取结果 MUST 一致

### Requirement: Overlay context remains correct under dense base context
当 base context 为 Dense path 时，overlay context MUST 保持既有语义：
- 读取优先 overlay，缺失回退 base。
- 写入仅落到 overlay，不影响 base。

#### Scenario: overlay reads fall back to base
- **WHEN** base 已设置某字段值且 overlay 未覆盖该字段/行
- **THEN** overlay 的读取 MUST 返回 base 值
