## Context
需要把现有 Hook 事件从“进程内观察”升级为“可触发下游动作”的标准事件流,以支持异步聚合、监控与外部对接.同时需整理内置事件与 Hook 的清单,降低集成成本.v1 仅通过 IR/Python 配置.

## Goals / Non-Goals
- Goals:
  - 事件具备统一封装(元数据 + 负载 + 类型)
  - 支持异步投递与可插拔传输层
  - 提供内置事件/Hook 的可查询目录
  - 不阻塞主流程,可配置背压与失败策略
- Non-Goals:
  - v1 不新增 YAML DSL 配置
  - v1 不强制引入外部依赖或分布式系统

## Options Considered
1) **统一事件包 + 异步投递(推荐方向)**
   - HookManager 将事件包装为统一事件包,交给 EventBridge/Transport 异步投递.
   - 优点: 对接标准化;可复用传输策略;最小侵入.
   - 缺点: 需要定义事件包与背压策略.

2) **自定义 Hook 直接对接外部系统(现状延伸)**
   - 用户自行实现 Hook,在回调内直接发 MQ/HTTP.
   - 优点: 快速;无需框架变更.
   - 缺点: 易阻塞主流程;缺乏统一元数据与治理.

3) **Outbox/落盘事件 + 外部消费**
   - 事件先落盘/写入本地队列,外部进程消费.
   - 优点: 更可靠;可解耦.
   - 缺点: 需要额外存储管理与清理策略.

## Decisions
- Decision: 采用“统一事件包 + 异步投递”作为主方案,并保留落盘/Outbox 作为可选传输实现.
- Decision: 提供事件目录(事件类型、字段、语义)作为稳定接口的一部分.
- Decision: 事件桥接启用与投递语义应可配置,失败/背压策略可配置(丢弃/降采样/阻塞/失败即停).
- Decision: 增加可靠模式,使用持久化 Outbox/落盘事件日志实现“完整不丢”,支持重启续投;Outbox 写入失败时应快速失败.

## Risks / Trade-offs
- 事件负载过大: 需要 payload 策略与采样策略.
- 异步失败: 需要重试/降级/告警机制.
- 事件一致性: 需明确“至少一次/至多一次”语义.
- Outbox 磁盘空间: 需要容量规划与告警;磁盘耗尽时会触发失败或阻塞策略.

## Migration Plan
- 评估对现有 Hook 行为与事件顺序的影响,如有变化提供迁移说明.
- 先提供 IR/Python 入口,后续再评估 DSL 扩展.

## Open Questions
- 事件包是否需要全局 run_id/trace_id? 若有,如何生成与传播?
- 不同事件类型是否需要独立的采样与节流策略?
- 并行模式下的事件顺序与一致性如何定义?
- 可靠模式下 Outbox 的保留与清理策略如何定义?
- 启用策略与投递语义是否需要默认值? 若需要,在调研后确定.

## Reference Examples

### Example: 查询内置事件目录(当前已具备 catalog 雏形)
```python
from IMPL_ROOT.events.catalog import get_event_catalog

for desc in get_event_catalog():
    print(desc.name, desc.volume, desc.payload_type)
```

### Example: 对外投递的统一事件包(JSON 形态示意)
```json
{
  "event_type": "loader_call",
  "timestamp": 1700000000.123,
  "run_id": "run_1700000000123",
  "seq": 42,
  "meta": {
    "batch_num": 3,
    "worker_id": "thread-1"
  },
  "payload": {
    "loader_name": "customers",
    "duration": 0.018,
    "cache_status": "miss"
  }
}
```

### Example: 可靠模式(outbox)落盘布局(示意)
```text
.scales_outbox/
  run_1700000000123/
    000001.jsonl   # append-only
    000001.ack     # last-acked seq or byte offset
```

### Example: 异步触发(“订单明细事件 -> 触发供应商汇总”)
```text
主流程:
  RowSink.write_row(row) 产生订单明细
  EventBridge.enqueue(event(order_created, payload=row_key + minimal fields))

异步消费者:
  消费事件 -> 触发另一条 PROJECT_DIST_NAME run(汇总 demand) 或写入外部系统
```
