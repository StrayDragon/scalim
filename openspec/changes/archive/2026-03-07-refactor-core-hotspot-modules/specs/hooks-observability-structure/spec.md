## ADDED Requirements

### Requirement: hooks 与 observer managers 必须按内部职责拆分
系统 MUST 允许将 `HookManager` 与 `ObserverManager` 的“订阅注册管理、handler 解析/缓存、高频事件分发、状态恢复”拆分为内部职责子模块,不得继续要求这些职责长期聚合在 `hooks/base.py` 与 `ob/manager.py` 单一热点文件内.

#### Scenario: managers 拆分后职责可审计
- **WHEN** 维护者重构 `HookManager` 或 `ObserverManager` 的内部结构
- **THEN** 注册、缓存、分发、状态恢复职责 MUST 可区分并独立审阅
- **AND** 不得重新把上述职责聚回单一热点实现

### Requirement: managers 内部拆分后必须保持行为语义稳定
系统 MUST 在 `HookManager` / `ObserverManager` 内部拆分后继续保持 wants 语义、缓存复用语义、线程安全语义与 pickle roundtrip 语义稳定.

#### Scenario: managers 行为语义保持稳定
- **WHEN** 完成 managers 内部职责拆分后运行相关测试
- **THEN** wants、缓存复用、线程安全与 pickle roundtrip 行为 MUST 与重构前保持一致
