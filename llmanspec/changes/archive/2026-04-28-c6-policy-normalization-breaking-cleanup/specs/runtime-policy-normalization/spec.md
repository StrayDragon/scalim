## ADDED Requirements

### Requirement: policy values MUST normalize to builtin str literals at state/serialization boundaries

对外可配置的 policy-like 值(封闭集合) MUST 在进入系统内部状态与序列化边界前被归一化为稳定的内置 `str` 字面量值,并满足:
- 允许值集合 MUST 为封闭集合(由 `Literal[...]` 或等价 SSOT 定义)
- normalize 函数 MUST fail-fast 于未知值,并在错误信息中列出允许值
- manager/state 等会被 pickling/序列化的对象图中 MUST 不包含 enum 实例

#### Scenario: manager state stores policy values as builtin str
- **WHEN** 系统构造 `HookManager`/`ObserverManager` 并进入其可序列化状态边界
- **THEN** 相关 policy 字段 MUST 为内置 `str` 值(而非 enum 实例)

### Requirement: normalize functions MUST be reused as SSOT

系统 MUST 为每个 policy-like 值提供 SSOT 的 `normalize_<policy>(...)` 实现,并要求所有入口/派生逻辑复用该 normalize。

#### Scenario: different entrypoints converge to the same normalized value
- **GIVEN** 调用方以不同大小写或连字符形式传入 policy 值(例如 `"drop-oldest"`)
- **WHEN** 系统在任意入口解析该值
- **THEN** normalize MUST 产生同一个稳定内置 `str` 值
