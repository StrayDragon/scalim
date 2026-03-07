## ADDED Requirements

### Requirement: HookManager 与 ObserverManager 的内部职责拆分必须可审计
系统 MUST 将 `HookManager` 与 `ObserverManager` 的“订阅注册管理、handler 解析/缓存、高频事件分发、状态恢复”视为独立职责,并允许通过内部子模块组织这些职责,而不是继续在单一热点文件中无限聚合.

#### Scenario: 内部职责可以拆入子模块
- **WHEN** 维护者重构 `HookManager` 或 `ObserverManager` 的内部实现
- **THEN** 系统 MUST 允许将注册、缓存、分发、状态恢复拆入内部子模块
- **AND** 不得要求这些职责继续长期共存于单一热点文件中

### Requirement: Hook 与 Observer 管理器重构后必须保持稳定入口与行为语义
系统 MUST 在 `HookManager` / `ObserverManager` 内部拆分后继续保持稳定导入入口与既有行为语义,至少包括: wants 语义、缓存复用语义、线程安全语义与 pickling 后锁恢复语义.

#### Scenario: 稳定入口继续可用
- **WHEN** 调用方继续通过既有稳定入口导入 `HookManager` 或 `ObserverManager`
- **THEN** 导入 MUST 成功
- **AND** 调用方不应被要求迁移到新的内部私有路径

#### Scenario: 行为语义保持稳定
- **WHEN** 完成内部职责拆分后运行现有 hooks / observer 管理器相关测试
- **THEN** wants、缓存复用、线程安全与 pickle roundtrip 语义 MUST 与重构前保持一致
