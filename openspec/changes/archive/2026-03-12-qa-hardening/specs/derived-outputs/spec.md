## ADDED Requirements

### Requirement: `max_groups=0`(不设上限)时必须输出明确 warn
当派生聚合输出的 `max_groups=0` 表示“不设上限”时,系统 MUST 输出明确的 warn,提示高基数 group-by 可能导致聚合状态无限增长并拖垮内存.

该 warn MUST 仅作为告警,不得改变结果语义(仍信任用户配置).

#### Scenario: 无上限聚合触发 warn
- **GIVEN** 某个派生输出配置 `max_groups=0`
- **WHEN** 运行开始执行派生聚合
- **THEN** 系统 MUST 输出一次 warn 提示资源耗尽风险并建议设置 `max_groups`
