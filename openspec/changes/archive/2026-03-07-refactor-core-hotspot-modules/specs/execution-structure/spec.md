## ADDED Requirements

### Requirement: adaptive scheduler 热点必须进一步拆分为可替换协作单元
系统 MUST 将 `execution/adaptive/loadref_scheduler.py` 视为确认热点,并允许其继续拆分为更清晰的协作单元,至少包括策略/worker 数解析、layer planning、任务提交、结果聚合与提交顺序维护.

#### Scenario: scheduler 拆分后协作单元边界清晰
- **WHEN** 维护者重构 `AdaptiveLoadRefScheduler` 的内部结构
- **THEN** 策略解析、任务提交与结果聚合 MUST 可独立测试
- **AND** 不得要求单一热点调度器长期同时承载上述全部职责

### Requirement: scheduler 热点拆分后输出与事件顺序保持稳定
系统 MUST 在 `loadref_scheduler.py` 拆分后继续保持相同输入下的输出顺序、事件回放顺序与错误语义不变.

#### Scenario: scheduler 结构重构后行为等价
- **WHEN** 完成 adaptive scheduler 的内部职责拆分
- **THEN** 相同输入下的输出顺序、事件顺序与错误语义 MUST 与重构前保持一致
