# 2026-07-19: event-type-enum-identity

## 变更摘要

进程内事件身份与 Observer / Hook 订阅面以 `EventType` 为唯一来源;类型化 `payload` 由 `scalim.events` 公开导出。

无兼容层:旧的裸 `str` 订阅与依赖非公开实现模块导入 `payload` 的写法需要主动迁移。

| 项 | 说明 |
|----|------|
| Breaking | `Event.event_type` 进程内为 `EventType` |
| Breaking | `Observer.event_types` / Hook `event_types` 为 `Optional[Set[EventType]]`;裸 `str` 注册 raise `TypeError` |
| Breaking | 稳定导入改为 `from scalim.events import <PayloadEvent>`(勿依赖非公开实现模块路径) |
| Added | `parse_event_type(...)`: 仅用于落盘 / `JSONL` / viz / capture **读回**时把 builtin `str` 归一为 `EventType` |
| Unchanged (语义) | `EventType` 成员对应的稳定字符串取值(`.value`) |
| Unchanged (边界) | `Event.to_dict()` 仍输出 builtin `str` 形式的 `event_type` |

规范引用:
- `llmanspec/changes/archive/2026-07-19-c0-event-type-enum-identity/`
- `llmanspec/specs/hooks-observability-structure/spec.toon`
- `llmanspec/specs/hooks-events/spec.toon`

---

## 如何判断是否受影响

在自己的代码中搜索下列模式;命中任一项即按后文对应 API 小节调整。

```text
event_types\s*=
Set\[str\].*event
"pipeline\.|"batch\.|"loader\.|"workflow_
from scalim\.events\._
event\.event_type\s*==\s*[\"']
event\.event_type\s+in\s*\{
\.to_dict\(\)
parse_event_type
supports_unknown_event_types
EventDispatchObserver|BaseHook|Observer\)
```

---

## 按 API 调整

复制示例时只使用 **After**;Before 仅表示旧写法。

### A. `Observer.event_types` / Hook `event_types`

**若使用:** 自定义 `Observer` / `EventDispatchObserver` / `BaseHook`(或其它 Hook)并设置 `event_types`。

**调整:** 集合元素必须是 `EventType` 成员;类型注解改为 `Optional[Set[EventType]]`。

Before:

```python
from scalim.ob.observer import EventDispatchObserver

class MyObserver(EventDispatchObserver):
    event_types = {"pipeline.start", "batch.start", "batch.end"}
```

After:

```python
from scalim.events import EventType
from scalim.ob.observer import EventDispatchObserver

class MyObserver(EventDispatchObserver):
    event_types = {
        EventType.PIPELINE_START,
        EventType.BATCH_START,
        EventType.BATCH_END,
    }
```

运行时错误示例:
- `TypeError: ... must contain only EventType; got str element ...`
- `... must be None or Set[EventType]`

---

### B. `scalim.events` 类型化 `payload` 导入

**若使用:** `PipelineStartEvent` / `BatchEndEvent` / `LoaderCallEvent` / workflow 相关 `*Event` 等类型化负载,且从非公开路径导入。

**调整:** 一律从包根导入。

Before:

```python
from scalim.events._events import PipelineStartEvent, BatchEndEvent
```

After:

```python
from scalim.events import PipelineStartEvent, BatchEndEvent
```

可用成员以 `scalim.events.__all__` / `docs/doc/getting-started/public-api.gen.md` 为准。

---

### C. `EventDispatchObserver.on_*` / Hook typed 回调

**若使用:** 覆盖 `on_pipeline_start`、`on_loader_call` 等 typed handler。

**调整:** 参数类型使用公开 `payload` 类;订阅集仍须满足 A。

```python
from scalim.events import EventType, PipelineStartEvent, LoaderCallEvent
from scalim.ob.observer import EventDispatchObserver

class MyObserver(EventDispatchObserver):
    event_types = {EventType.PIPELINE_START, EventType.LOADER_CALL}

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        _ = event.targets

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        _ = event.loader_name
```

---

### D. `Event.event_type` 读取与比较

**若使用:** 在 `on_event` 或其它路径读取 / 比较 `event.event_type`。

**调整:**
- 注解与分支优先使用 `EventType`
- 与字符串字面量比较在运行上常因 `str` 子类仍成立,但作者面应迁到 Enum,避免混用两套身份

```python
from scalim.events import Event, EventType

def handle(event: Event) -> None:
    if event.event_type is EventType.PIPELINE_START:  # 或 == EventType.PIPELINE_START
        ...
```

---

### E. `Event.to_dict` / JSONL / capture / viz 读回

**若使用:** 序列化事件后再构造进程内 `Event`,或手写解析 `event_type` 字段。

**调整:** 边界字符串经 `parse_event_type` 再进入进程内。

```python
from scalim.events import EventType, parse_event_type

wire = event.to_dict()  # wire["event_type"] 为 builtin str
identity = parse_event_type(wire["event_type"])  # EventType
```

注意:
- `parse_event_type` **不是**注册订阅的入口;不要用它给 `event_types` 塞字符串绕过严进
- 未知字符串会 `ValueError`

---

### F. `InstrumentationHub.wants` / `emit` / manager 分发

**若使用:** 直接调用 hub / manager 的 `wants` / `emit` / `emit_typed`(扩展或测试工具)。

**调整:** 传入 `EventType` 成员,而不是作者面裸字符串。

```python
hub.wants(EventType.LOADER_CALL)
hub.emit(EventType.PIPELINE_START, payload)
```

---

### G. `EventType` / `type_groups` / `get_event_catalog`

**若使用:** 枚举或按主题发现事件种类。

**调整:** 无破坏性;继续作为推荐发现入口。

```python
from scalim.events import EventType, get_event_catalog, type_groups

EventType.PIPELINE_START
type_groups.pipeline.start
get_event_catalog()
```

---

### H. `supports_unknown_event_types`

**若使用:** 依赖“目录外任意字符串事件名”的订阅。

**调整:** 稳定扩展应先登记 `EventType` 与事件目录。该标志仅作逃生口,不是推荐公共扩展方式。

---

## 通常无需改动的 API

下列用法不因本批次而要求修改(除非同时触达上面 A–F):

| API / 用法 | 说明 |
|------------|------|
| `scalim.dsl.yaml_dsl.run` / `run_workflow` | 运行入口本身不变 |
| `DemandRunOptions` / `WorkflowRunOptions` 等 Options 字段 | 与本批次无关 |
| `PerformanceObserver` / `LoggingObserver` / `MemoryOptimizationObserver` 等 presets 的常规构造 | 内部订阅已对齐 `EventType` |
| `latest_book_path` / `book_sheet_rows` / `derive_base_module_path` | 与事件身份无关 |
| `EventType` 成员的 `.value` 字符串取值 | 保持稳定,便于边界编码 |

---

## 最小自检

1. 自定义 Observer/Hook 的 `event_types` 仅含 `EventType` 成员
2. `payload` 类型从 `scalim.events` 导入
3. 注册后跑通一次 `run` 或 `run_workflow`(或等价 `run_ir` + `components`)
4. 若有自建序列化读回路径,确认使用 `parse_event_type`

仓库内可参考示例:
- `notebooks/marimo/example_public_api_suite/chapters/ch180_public_api_hooks_events.py`
- `notebooks/marimo/example_public_api_suite/chapters/ch182_public_api_event_type_groups.py`
