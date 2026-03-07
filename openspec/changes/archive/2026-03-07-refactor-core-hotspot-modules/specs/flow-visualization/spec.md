## ADDED Requirements

### Requirement: VizObserver 热点必须分离配置、事件建模、快照增强与文件输出职责
系统 MUST 允许将 `ob/presets/viz.py` 按职责拆分为内部协作单元,至少包括配置/路径解析、执行事件到 VizEvent 的映射、快照与 meta 增强、文件输出/落盘.

#### Scenario: viz 热点拆分后职责边界清晰
- **WHEN** 维护者重构 `VizObserver` 相关实现
- **THEN** 配置解析、事件建模、快照增强与文件输出职责 MUST 可区分并独立审阅
- **AND** 不得继续要求这些职责长期聚合于单一热点模块

### Requirement: viz 热点拆分后输出契约保持稳定
系统 MUST 在 `ob/presets/viz.py` 内部拆分后继续保持 `viz_snapshot.json`、`viz_events.jsonl`、`viz_trace.jsonl` 的文件结构与既有产出契约稳定.

#### Scenario: viz 结构重构后产出契约保持一致
- **WHEN** 完成 `VizObserver` 内部职责拆分并生成可视化产物
- **THEN** 输出文件结构、关键字段与既有回放契约 MUST 与重构前保持兼容
