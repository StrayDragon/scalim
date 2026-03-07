## Why

`src/IMPL_ROOT/hooks/base.py` 与 `src/IMPL_ROOT/ob/manager.py` 已同时承载“注册管理、分发缓存、热路径分发、线程安全、序列化恢复”等多种职责,继续在单文件内增长会提高 review、回归与后续重构成本.

当前最合适的下一步重构不是触碰 DSL / execution 主链,而是先对 Hook / Observer 管理器做 phase 1 结构治理:把内部职责拆开,同时保持外部稳定入口与运行语义不变.

## What Changes

- 对 `HookManager` 与 `ObserverManager` 开展 phase 1 结构重构提案,聚焦“注册管理 / 分发策略 / handler 缓存 / pickling 恢复”职责拆分.
- 保持现有稳定导入入口与主要运行语义不变,避免把结构重构升级成公共 API 变更.
- 补充针对模块组织、热路径缓存与兼容导入的规范增量,使后续实现与 review 有清晰边界.
- 明确该 change 仅覆盖 hooks / observability manager 相关热点,不在本 change 内同时拆分 YAML runtime、adaptive scheduler 等其它大模块.

## Capabilities

### New Capabilities

### Modified Capabilities
- `hooks-observability-structure`: 明确 HookManager / ObserverManager 的内部职责拆分要求、热路径缓存边界与稳定导入承诺.
- `module-organization`: 明确热点模块 phase 1 重构可以先从 hooks / ob manager 切入,并要求内部拆分后继续保持稳定入口.

## Impact

- 受影响代码主要位于 `src/IMPL_ROOT/hooks/base.py`、`src/IMPL_ROOT/ob/manager.py` 及其配套测试.
- 受影响规范为 `openspec/specs/hooks-observability-structure/spec.md` 与 `openspec/specs/module-organization/spec.md` 的增量要求.
- 预期不引入新的用户侧配置项,不改变 `components` 装配方式,不改变事件目录与既有 Hook/Observer 的基本语义.
