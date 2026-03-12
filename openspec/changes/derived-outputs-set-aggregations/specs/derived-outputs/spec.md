## ADDED Requirements

### Requirement: 内置 set 口径聚合原语
系统 SHALL 在 `derived-outputs` 的内置聚合能力中新增 streaming-friendly 的 set 口径原语,用于减少业务侧 Python state 并提升复用性.

系统 MUST 至少支持:
- `count_distinct(field_id=...)`(支持复合 key)
- `dedup_by(key_fields=..., on_conflict=error|first|last)`
- `two_stage_group_by(stage1=..., stage2=...)`

#### Scenario: `count_distinct` 统计 distinct 用户数
- **GIVEN** 详情流包含 `cs_id` 与 `user_id`
- **WHEN** 派生输出按 `cs_id` 分组并对 `user_id` 执行 `count_distinct`
- **THEN** 系统 MUST 输出每个 `cs_id` 的 distinct 用户数且结果确定性

### Requirement: `dedup_by` 冲突策略必须确定且可对拍
系统 MUST 对 `dedup_by` 在同一 key 命中多行时的冲突策略提供显式配置,并保证在相同输入下结果确定性.

#### Scenario: `dedup_by.on_conflict=first`
- **GIVEN** 两行数据具有相同的 dedup key
- **WHEN** 配置 `dedup_by(..., on_conflict=first)`
- **THEN** 系统 MUST 选择稳定的“第一条”并用于后续指标计算

### Requirement: 两阶段聚合固定 tie-break 与输出顺序
系统 MUST 为 `two_stage_group_by` 的 stage1/stage2 均定义确定性的 tie-break 与输出顺序规则,以避免对拍误报.

#### Scenario: stage1 先按 `user_id` 聚合再按 `cs_id` 汇总
- **WHEN** stage1 按 `user_id` 累计 `pay_order_cnt`
- **AND** stage2 按 `cs_id` 统计 `count_true(pay_order_cnt>=2)`
- **THEN** 系统 MUST 在相同输入下产生相同输出(含顺序)

### Requirement: distinct/去重状态的资源护栏与诊断
系统 SHALL 为 `count_distinct`/`dedup_by`/`two_stage_group_by` 提供可配置护栏,并在触发时给出可对拍的诊断信息(例如 distinct key 数量/截断信息/稳定指纹).

#### Scenario: distinct 护栏不设上限触发 warn
- **GIVEN** 用户将 distinct 护栏配置为不设上限(例如 `max_distinct=0`)
- **WHEN** 运行开始执行 set 口径聚合
- **THEN** 系统 MUST 输出一次 warn 提示高基数风险,但不得改变结果语义
