## ADDED Requirements

### Requirement: 热点模块 phase 1 重构可以从 hooks 与 observability managers 独立推进
系统 MUST 允许将热点模块治理拆分为多个 phase 独立推进;当维护者先处理 `hooks` / `ob` managers 时,不得强制与其它热点模块在同一 change 中一起重构.

#### Scenario: hooks / ob managers 可以单独作为一轮重构
- **WHEN** 维护者选择先重构 `HookManager` / `ObserverManager` 相关热点模块
- **THEN** 系统 MUST 允许该 change 仅覆盖 hooks / observability managers
- **AND** 不应要求同一 change 同时包含 YAML runtime、adaptive scheduler 或其它热点模块的拆分

### Requirement: 热点模块内部拆分后必须保持官方稳定入口不变
系统 MUST 在热点模块内部拆分后继续保持官方稳定入口可用;对于 `HookManager` / `ObserverManager` 这类已被测试和调用路径依赖的核心类型,实现拆分不得改变推荐导入路径.

#### Scenario: 内部重构不改变推荐导入路径
- **WHEN** `HookManager` / `ObserverManager` 的实现被拆入新的内部模块或 package
- **THEN** 调用方通过当前推荐导入路径 MUST 继续可用
- **AND** 模块布局测试 SHOULD 覆盖该稳定入口承诺
