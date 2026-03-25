## Why
当前 hook/event 只能在本地进程内使用,难以作为“触发器”连接外部系统或其他 PROJECT_NAME 实例,导致:
- 异步聚合/增量计算需要额外手工 glue code
- 事件缺少统一元数据与目录,对接成本高
- 无法在不阻塞主流程的前提下可靠投递事件

**核心示例(异步触发):**
- 详情输出产生订单事件 → 异步触发另一个 PROJECT_NAME 进行供应商利润率汇总

**类似示例:**
- 运行进度事件 → 发送到监控系统/通知系统
- Loader 性能事件 → 持久化到监控指标仓库
- 诊断告警事件 → 触发风控或数据质量检查
- 批次完成事件 → 触发下游缓存刷新或指标热更新
- 明细行事件 → 触发流式特征计算或实时画像更新

## What Changes
- 引入事件桥接能力: 将 Hook 事件统一封装为标准事件包并支持异步投递(队列/HTTP/文件等可插拔传输).
- 增加事件目录与元数据: 提供内置事件/Hook 的可查询清单,便于集成与治理.
- v1 仅提供 IR/Python 配置入口;评估对现有 Hook 行为和事件顺序的影响,并提供显式启用/禁用控制.
- 增加“可靠模式”选项: 通过持久化 Outbox/落盘事件日志确保事件完整性,崩溃可恢复投递.

## Impact
- 受影响规范: hooks-events(新增事件目录/元数据要求),新增 event-bridge.
- 涉及组件: Hook 事件分发、可观测性事件包装、异步投递与失败策略.
- 主要风险: 事件负载过大、异步投递失败、背压影响主流程.

## Compatibility Notes (adaptive-execution-mode)

- `adaptive-execution-mode` 会将部分并发路径的 hooks/observers 触发切换为“提交点回放”(顺序稳定但非实时).event-bridge 设计与可靠模式(outbox/backpressure)应以“事件在提交点批量产生”为常见形态来评估负载与背压.

## Calibration Notes (2026-03-25)

- 事件目录已相当成熟:`src/scalim/events/catalog.py` 包含 27 种事件类型(`EventDescriptor`),覆盖 pipeline/batch/loader/field/row/workflow-node/workflow-cache/workflow-resource 全链路
- `get_event_catalog()` / `get_event_catalog_map()` API 已可用,proposal 中的"事件目录"目标已部分实现(仅缺对外投递能力)
- hooks 系统(`src/scalim/hooks/`)包含 dispatch/manager_registry/manager_events/manager_subscriptions 等,结构已稳定
- 如果启动此提案,建议从"最小异步投递 + 事件目录标准化 CLI 导出"切片开始,不需要一次性实现完整的 outbox/backpressure/reliable mode
<<<<<<<< HEAD:openspec/notplan-changes/c999-hook-event-bridge/proposal.md
- SSOT 归属注意: delta spec `hooks-events/spec.md` 中的"事件目录与元数据"requirement 与 `hooks-observability-structure` spec 存在 SSOT 重叠——后者已管辖 `EventDescriptor`/`InstrumentationHub`/事件分发路径。如启动此提案,事件目录/元数据应继续归属 `hooks-observability-structure`,本提案的新增 requirement 应仅聚焦在"event-bridge 异步投递"能力本身（已有独立 delta spec `event-bridge/spec.md`）
========
>>>>>>>> f169a62 (Squash commits from feat-yaml-dsl-public-tools):openspec/notplan-changes/c60-hook-event-bridge/proposal.md
