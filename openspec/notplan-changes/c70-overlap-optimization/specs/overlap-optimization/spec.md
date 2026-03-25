## ADDED Requirements
### Requirement: 重叠键复用
系统 SHALL 支持在相邻批次之间复用关联查询的结果,以减少重复 loader 调用.

#### Scenario: 批次间命中重叠键
- **WHEN** 相邻批次的关联键集合存在重叠
- **THEN** 系统应从复用缓存中直接返回已加载结果

### Requirement: 缓存边界与可控性
系统 SHALL 提供可配置的缓存边界 (容量或窗口),并在超出限制时进行淘汰.

#### Scenario: 缓存超出限制
- **WHEN** 缓存超过设定容量
- **THEN** 系统应按约定策略淘汰旧的关联结果

## Notes
- 具体缓存策略与默认值待实现阶段确定 (TODO).
