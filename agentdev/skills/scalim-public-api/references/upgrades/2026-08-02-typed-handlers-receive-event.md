# 2026-08-02: typed-handlers-receive-event

## 变更摘要

typed Observer / Hook 回调（`on_field_compute` 等）进程内入参改为完整 `Event` envelope，不再只传入 `event.payload`。

横切字段（含 `meta.scalim_compute_phase`、workflow 归因）可在 typed 路径直接读取；公开 payload 类型经 `event.payload` 消费。

无兼容层：不要长期依赖「payload 与 Event 双签名」分发。

| 项 | 说明 |
|----|------|
| Breaking | typed `on_*` 入参为 `Event`（不是公开 payload dataclass） |
| Unchanged | `IExecutionHook.on_event(Event)` 与 typed 并存语义 |
| Unchanged | `Event.payload` 仍为公开 `*Event` payload 类型 |
| Unchanged | `Event.to_dict()` / JSONL 边界仍输出 builtin `str` 身份 |

规范引用:
- `llmanspec/changes/c35-typed-handlers-receive-event/`（归档后见 `archive/…`）
- `llmanspec/specs/hooks-observability-structure/spec.toon`（r217）

---

## 如何判断是否受影响

在自己的代码中搜索下列模式;命中任一项即按后文调整。

```text
def on_pipeline_start\(self,\s*event
def on_field_compute\(self,\s*event
def on_loader_call\(self,\s*event
EventDispatchObserver|BaseHook
event\.targets|event\.field_key|event\.loader_name
```

若 typed handler 内直接读 payload 字段（如 `event.field_key`），升级后会变成对 `Event` 的属性访问而失败或语义错误。

---

## 按 API 调整

### A. typed Observer / Hook：入参改为 `Event`

**若使用:** 覆盖 `EventDispatchObserver.on_*` 或 Hook typed `on_*`。

**调整:** 注解为 `Event`；业务字段经 `event.payload`；横切经 `event.meta`。

Before:

```python
from scalim.events import EventType, FieldComputeEvent
from scalim.ob.observer import EventDispatchObserver

class MyObserver(EventDispatchObserver):
    event_types = {EventType.FIELD_COMPUTE}

    def on_field_compute(self, event: FieldComputeEvent) -> None:
        _ = event.field_key
        _ = event.result
```

After:

```python
from scalim.events import Event, EventType, FieldComputeEvent
from scalim.ob.observer import EventDispatchObserver

class MyObserver(EventDispatchObserver):
    event_types = {EventType.FIELD_COMPUTE}

    def on_field_compute(self, event: Event) -> None:
        payload = event.payload  # FieldComputeEvent
        assert isinstance(payload, FieldComputeEvent)
        _ = payload.field_key
        _ = payload.result
        phase = event.meta.get("scalim_compute_phase")  # 例如 operator / write_precompute
```

Hook 侧同理：`BaseHook.on_field_compute(self, event: Event)`。

### B. 只需读 phase / workflow 归因时不必再绕 `on_event`

**若使用:** 仅为读取 `Event.meta` 而覆写 `on_event`。

**调整:** typed `on_*` 已能读同一 `Event.meta`；可保留 `on_event` 做通配处理，但不必仅为 phase 绕道。

---

## 交叉入口

- 本 skill：`task-event-type-adaptation.md`（EventType 身份批次仍见 `2026-07-19-event-type-enum-identity.md`）
- 人类文档：`docs/doc/viz/scalim-viz.md`、`docs/doc/releases/0.10.0/`
- 示例：`ch180_public_api_hooks_events`（若仍有 payload 直读，按本节 A 迁移）
