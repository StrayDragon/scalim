# hooks-observability-structure Specification (Delta)

## ADDED Requirements

### Requirement: events public facade MUST provide structured access to event types

系统 MUST 为用户提供结构化的事件类型访问方式，以降低平铺常量导入造成的学习与维护成本，同时保持 `event_type` 字符串值稳定。

系统 MUST 满足：

- `scalim.events` MUST 提供一个可枚举/可检索的事件目录入口（例如 `get_event_catalog`）。
- `scalim.events` SHOULD 提供按主题分组的稳定入口（例如 `pipeline/workflow/loader/diagnostic` 分组对象或等价结构），避免要求用户直接导入大量平铺常量。

#### Scenario: user can enumerate known event types without importing internal payload types
- **WHEN** 用户调用 `scalim.events.get_event_catalog()`
- **THEN** 系统 MUST 返回一个可枚举的事件目录结构
- **AND** 用户 MUST 能仅通过 `event_type` 与 `Event.payload` 的字段/键消费数据，而无需导入 typed payload 数据类
