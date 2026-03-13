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

### Requirement: `count_distinct` 复合 key 与缺失值语义
系统 MUST 支持 `count_distinct` 同时接受:
- 单字段 distinct: `count_distinct(field_id=...)`
- 复合 key distinct: `count_distinct(field_ids=(...))`

系统 MUST 明确缺失值语义,并保证对拍友好:
- 当 distinct key 的任一组成字段为 `None` 时,该行 MUST 被忽略(对齐 SQL `COUNT(DISTINCT)` 的 `NULL` 语义).
- 空字符串 `""` MUST 作为普通值参与 distinct.

#### Scenario: 复合 key 的缺失值忽略
- **GIVEN** distinct key 由 `cs_id` 与 `user_id` 组成
- **WHEN** 某行的 `user_id` 为 `None`
- **THEN** 系统 MUST 忽略该行且不计入 distinct 计数

### Requirement: `dedup_by` 冲突策略必须确定且可对拍
系统 MUST 对 `dedup_by` 在同一 key 命中多行时的冲突策略提供显式配置,并保证在相同输入下结果确定性.

#### Scenario: `dedup_by.on_conflict=first`
- **GIVEN** 两行数据具有相同的 dedup key
- **WHEN** 配置 `dedup_by(..., on_conflict=first)`
- **THEN** 系统 MUST 选择稳定的“第一条”并用于后续指标计算

### Requirement: `adaptive` 下的确定性边界(顺序依赖语义 fail-fast)
系统 MUST 明确 `parallel_mode="adaptive"` 下的确定性边界: 任一阶段包含顺序依赖语义时,系统 MUST fail-fast 并提示切换到 `parallel_mode="seq"` 或改用非顺序依赖配置.

系统 MUST 至少包含下列规则:
- `dedup_by.on_conflict=first|last` 属于顺序依赖语义,在 `adaptive` 下 MUST fail-fast.
- `dedup_by.on_conflict=error` 在 `adaptive` 下 MUST 允许(仍保持确定性,且错误信息不得泄露敏感 key 值).

#### Scenario: `adaptive` 下拒绝顺序依赖去重策略
- **WHEN** `parallel_mode="adaptive"` 且 `dedup_by.on_conflict=first`
- **THEN** 系统 MUST fail-fast 并提示切换到 `parallel_mode="seq"`

### Requirement: 两阶段聚合固定 tie-break 与输出顺序
系统 MUST 为 `two_stage_group_by` 的 stage1/stage2 均定义确定性的 tie-break 与输出顺序规则,以避免对拍误报.

#### Scenario: stage1 先按 `user_id` 聚合再按 `cs_id` 汇总
- **WHEN** stage1 按 `user_id` 累计 `pay_order_cnt`
- **AND** stage2 按 `cs_id` 统计 `count_true(pay_order_cnt>=2)`
- **THEN** 系统 MUST 在相同输入下产生相同输出(含顺序)

### Requirement: distinct/去重状态的资源护栏与溢出策略
系统 SHALL 为 set 口径状态提供可配置护栏,用于限制聚合状态规模并提供可对拍诊断信息.

系统 MUST 支持:
- `max_distinct`: distinct key 数上限(0 表示不设上限)
- `on_overflow`: 溢出策略(至少支持 `error|truncate`)

系统 MUST 满足:
- 当 `max_distinct=0` 表示“不设上限”时,系统 MUST 输出一次明确 warn(仅告警,不得改变结果语义).
- 当 `on_overflow=error` 且 distinct key 数超过上限时,系统 MUST fail-fast 并给出可操作错误提示.
- 当 `on_overflow=truncate` 时:
  - 系统 MUST 以确定性方式截断(同一输入下结果可对拍;不得依赖不稳定的输入顺序).
  - 系统 MUST 记录截断发生的结构化审计信息(不得泄露明细 key 值).

#### Scenario: distinct 护栏不设上限触发 warn
- **GIVEN** 用户将 distinct 护栏配置为不设上限(例如 `max_distinct=0`)
- **WHEN** 运行开始执行 set 口径聚合
- **THEN** 系统 MUST 输出一次 warn 提示高基数风险,但不得改变结果语义

### Requirement: 最小条件计数原语(支持 `repeat_paid_users`)
系统 MUST 提供至少一种“可对拍且可指纹化”的条件计数能力,用于覆盖 `repeat_paid_users` 等常见口径.

系统 MUST 至少支持:
- `count_true_gte(field_id, threshold)`(当 `field_id` 的数值 >= threshold 时计数 +1)

#### Scenario: `count_true_gte` 阈值计数
- **GIVEN** 某行 `pay_order_cnt=2`
- **WHEN** 指标配置为 `count_true_gte(field_id="pay_order_cnt", threshold=2)`
- **THEN** 系统 MUST 对该行计数 +1

### Requirement: meta/audit 的稳定指纹与结构化审计
系统 MUST 为每个 derived target 生成稳定聚合指纹(不包含 callables/环境相关对象),并写入 meta sheet.

系统 MUST 满足:
- meta 中 MUST 写入: `derived.<target_id>.fingerprint`
- 当触发护栏失败/截断/冲突等情况时:
  - 系统 MUST 写入结构化 audit 行
  - audit 行 MUST 仅包含: 目标标识/配置指纹/计数统计/稳定的 message hash 等脱敏信息
  - audit 行 MUST NOT 泄露明细行内容与聚合 key 的具体值

#### Scenario: 写入派生聚合指纹到 meta
- **WHEN** 运行包含 derived target
- **THEN** 系统 MUST 在 meta 中写入 `derived.<target_id>.fingerprint`
