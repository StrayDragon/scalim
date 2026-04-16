## Why

事件体系（`scalim.events`）与可观测性门面（`scalim.ob`）是用户实现 Observer/Hook 的主要入口，但当前 public surface 的问题是：

- `scalim.events` 导出大量常量与零散工具，用户要写一个“只订阅少数事件”的 Hook 仍需要理解/记忆一大批符号名。
- `scalim.ob.Observability` 的构造参数与策略字段以 “magic strings + 多可选参数” 形式存在，缺少强类型 options 与 fail-fast 校验，容易把内部策略细节外溢成事实契约。

本 change 目标是：在不改变事件 envelope 与 dispatch 热路径语义的前提下，收敛 events/observability 的 public surface，提升可用性与可维护性，并使 public exports 更稳定、可审计。

## What Changes

- **BREAKING**：为 `scalim.events` 提供更结构化的稳定入口：
  - 将事件类型常量按主题分组（或提供等价的 catalog/namespace 对象），降低“平铺常量”造成的学习成本。
  - 保持用户侧以 `event_type` + `Event.payload` 消费数据，不引入对 typed payload 数据类导入路径的依赖。
- **BREAKING**：为 `scalim.ob.Observability` 引入强类型 options（或等价收敛）：
  - 以 options 对象承载策略字段，并对非法组合 fail-fast（错误信息指向字段路径）。
  - 保持执行层/DSL 层的装配边界清晰：组件装配仍以 `components=[Observer/Hook]` 为主线。
- 同步更新治理与用户材料：catalog/docs、import-boundary gate、tests/notebooks 示例一次性升级（不做兼容层）。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `hooks-observability-structure`: 明确 events/observability public facade 的组织方式与“用户材料不得依赖内部 payload 类型”的边界。
- `public-api-surface-governance`: events/ob 作为 Tier1 curated entrypoints，需要对 exports 的新增/移除/分组调整形成显式审计与门禁闭环。
- `public-api-manifest`: public API catalog/docs 需要反映新的 events/ob public surface（分组后的入口与导出面）。

## Impact

- 受影响代码：
  - `src/scalim/events/__init__.py` 与 events catalog 相关模块（exports 组织与分组）
  - `src/scalim/ob/observability.py` 与 `src/scalim/ob/__init__.py`（options 收敛）
- 受影响用户材料：
  - docs/skills/notebooks/tests 中对事件常量与 observability 的用法
- 风险：
  - public surface 变更，需一次性升级调用点（不做兼容层）
