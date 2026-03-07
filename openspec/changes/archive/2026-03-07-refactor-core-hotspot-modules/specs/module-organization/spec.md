## ADDED Requirements

### Requirement: 一次性热点重构可以在单个 change 中覆盖多个核心热点模块
系统 MUST 允许将多个已确认热点模块的结构重构放在单个 change 中统一规划与实施,前提是各热点仍通过显式 phase 与任务分组保持边界清晰.

#### Scenario: 单个 change 聚合多个热点模块
- **WHEN** 维护者决定一次性重构多个核心热点模块
- **THEN** 系统 MUST 允许单个 change 同时覆盖这些热点
- **AND** tasks MUST 通过显式 phase 或任务分组区分不同热点主线

### Requirement: 已确认热点模块必须按职责拆分并保持稳定入口
系统 MUST 将以下路径视为本轮一次性重构的确认热点,并要求其内部实现按职责拆分:
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validators/fields.py`
- `src/IMPL_ROOT/dsl/by_yaml/runtime/conversion.py`
- `src/IMPL_ROOT/hooks/base.py`
- `src/IMPL_ROOT/ob/manager.py`
- `src/IMPL_ROOT/ob/presets/viz.py`
- `src/IMPL_ROOT/execution/adaptive/loadref_scheduler.py`

拆分后,系统 MUST 保持这些热点相关的官方稳定入口继续可用,不得要求调用方迁移到新的内部私有路径.

#### Scenario: 热点拆分后稳定入口仍可用
- **WHEN** 上述任一热点模块被拆入新的内部子模块或 package
- **THEN** 通过当前官方稳定入口的导入 MUST 继续成功
- **AND** 调用方 MUST NOT 被要求直接导入新的内部私有模块
