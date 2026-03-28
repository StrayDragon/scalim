## MODIFIED Requirements

### Requirement: 观测事件契约集中
系统 MUST 以 `IMPL_ROOT.events` 作为事件定义中心,执行层、hooks、observers 通过统一 `Event` envelope 与稳定的 `event_type` + payload 字段语义交互,不得跨层依赖实现细节.

为避免“内部实现便利”反向固化为公共契约,系统 MUST 将 typed payload 数据类视为内部实现细节：

- docs/examples/skills 等用户可见材料 MUST NOT 依赖 payload 数据类的导入路径或类名作为长期契约。
- 用户侧订阅/分发以 `event_type`（及其常量/目录）为准,并通过 `Event.payload` 的稳定字段/键消费数据。

#### Scenario: 用户侧以 event_type 订阅且不导入 payload 类型
- **WHEN** 用户希望订阅 pipeline 生命周期事件
- **THEN** 用户侧 MUST 通过 `IMPL_ROOT.events` 的事件类型常量/目录（例如 `EVENT_PIPELINE_START`）表达订阅
- **AND** 用户侧 MUST 通过 `Event.payload` 的稳定字段/键（例如 `targets`/`batch_size`）消费负载,而不是依赖某个 payload 数据类的导入路径

