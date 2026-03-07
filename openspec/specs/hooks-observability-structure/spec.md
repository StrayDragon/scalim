# hooks-observability-structure Specification

**状态: ✅ 已实现**
## Purpose
定义 Hook/Observer/事件体系的统一边界:事件契约、分发路径、组件装配与高频路径性能语义.

## Related Code (as implemented)
- `src/IMPL_ROOT/events/catalog.py`
- `src/IMPL_ROOT/events/event.py`
- `src/IMPL_ROOT/events/events.py`
- `src/IMPL_ROOT/hooks/base.py` (`HookManager`)
- `src/IMPL_ROOT/ob/manager.py` (`ObserverManager`)
- `src/IMPL_ROOT/ob/hub.py` (`InstrumentationHub`)
- `src/IMPL_ROOT/ob/components.py` (`split_components`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/observability.py` (`compile_observability_spec`)
## Requirements
### Requirement: 观测事件契约集中
系统 MUST 以 `IMPL_ROOT.events` 作为事件定义中心,执行层、hooks、observers 通过统一 `Event` envelope 与 typed payload 交互,不得跨层依赖实现细节.

#### Scenario: 事件类型来源清晰
- **WHEN** 导入 `BatchStartEvent` 等事件
- **THEN** 统一从 `IMPL_ROOT.events` 获取

### Requirement: InstrumentationHub 是执行层唯一事件投递边界
系统 MUST 通过 `InstrumentationHub` 统一分发到 hooks/observers.
`wants(event_type)=false` 时 MUST 快速短路:不得构建 payload、不得构建 `Event` envelope、不得进入热路径额外开销.

#### Scenario: 无订阅者时无副作用
- **WHEN** 未注册订阅者且触发某事件 `emit(...)`
- **THEN** 系统 MUST 不调用回调且不构建高成本 payload

### Requirement: 组件列表是对外唯一装配入口
系统 MUST 通过统一 `components` 列表装配 hooks/observers;不得通过新增运行入口 bool 开关切换实现.
组件列表 MUST 支持混合 `Observer` 与 `IExecutionHook`.

#### Scenario: 追加组件即可订阅
- **WHEN** 用户在 components 中追加一个 hook 或 observer
- **THEN** 该组件 MUST 在对应事件触发时收到回调

### Requirement: 执行层与观测层解耦
系统 MUST 保持执行层仅依赖事件契约与分发器,不直接 import 具体观测实现.
execution 入口 MUST 消费 DSL-agnostic 的组件装配结果,不直接依赖 YAML 专有观测类型.

#### Scenario: execution 编排不依赖 YAML 观测模型
- **WHEN** 审阅 execution 编排入口的 imports/参数类型
- **THEN** 不应直接 import/依赖 `ObservabilityConfig` 等 YAML 专有配置类型

### Requirement: 观测预设实现必须分离采集建模与展示职责
系统 MUST 将 observability 预设实现按“事件采集、数据建模、展示/导出”职责分离组织,避免单个预设模块长期同时承载三类职责.

#### Scenario: 展示层替换不影响采集契约
- **WHEN** 维护者替换或调整可视化/导出实现
- **THEN** 事件采集契约 MUST 保持稳定
- **AND** 执行层与 hook 分发逻辑 MUST 不需要同步改动

#### Scenario: 采集策略调整不破坏展示输入契约
- **WHEN** 维护者调整采集策略实现
- **THEN** 输出给展示层的中间模型契约 MUST 保持稳定
- **AND** 展示层 MUST 能在不改调用方式下继续工作

### Requirement: HookManager 必须将注册管理与分发策略解耦
系统 MUST 将 HookManager 的“订阅注册管理”与“事件分发策略”视为独立职责并保持实现解耦,防止单一基类持续增长.

#### Scenario: 扩展分发策略不影响订阅注册
- **WHEN** 新增或调整事件分发策略
- **THEN** 订阅注册语义 MUST 保持不变
- **AND** 既有 hook 订阅行为 MUST 与重构前一致

### Requirement: 事件分发热路径以缓存 callable 为主
系统 MUST 在 HookManager 高频事件分发路径避免每次 `emit` 执行 `getattr/hasattr` 反射查找,并在注册阶段编译/缓存 callables 后直接分发.
Observer 分发路径 MAY 使用“首次事件懒绑定 + 后续缓存复用”的策略;该一次性反射查找不应在后续同类事件重复发生.

#### Scenario: Hook 高频分发无反射
- **WHEN** 高并发/高频事件被触发且存在 hook 订阅者
- **THEN** 分发路径应直接调用缓存的 callables,不在每次 emit 中执行 handler 反射查找

#### Scenario: Observer 首次懒绑定后复用缓存
- **WHEN** observer 首次接收某事件类型
- **THEN** 允许一次性解析 handler
- **AND** 后续同事件类型分发应复用缓存结果

### Requirement: Hook 的 on_event 与 typed 回调不互斥
系统 MUST 将 `IExecutionHook.on_event(Event)` 视为额外订阅方式,不得因实现 `on_event` 而禁用 typed 回调.
当 hook 同时实现 typed 与 `on_event`,系统 SHOULD 同时触发二者.

#### Scenario: 同时订阅 typed 与 on_event
- **WHEN** hook 同时覆写 `on_event` 与 `on_pipeline_start`
- **THEN** 触发 pipeline_start 时该 hook 的两条回调路径都应被调用

### Requirement: wants 语义仅表示订阅者存在
系统 MUST 保持 `wants(event_type)` 仅表示订阅者存在,不得混入 fallback logger 等副作用策略.

#### Scenario: fallback 不影响 wants
- **WHEN** 未注册 hooks/observers 但启用了诊断 fallback logger
- **THEN** `wants(EVENT_DIAGNOSTIC_WARNING)` 仍应为 false

### Requirement: Loader/Diagnostic 事件负载结构稳定
系统 MUST 提供稳定的 Loader 与 diagnostic 事件负载字段.
Loader 事件 MUST 支持 `full|summary|sample|none` 策略,且 `sample_size>=1`;`cache_status=hit` 时 MUST NOT 触发实际 loader 调用.
diagnostic warning payload 至少包含 `message`、`source_id`、`field_id`、`lookup_key`、`row_id`.

#### Scenario: summary 负载有效
- **WHEN** loader policy 为 `summary`
- **THEN** loader 事件 payload MUST 返回摘要结构(含 `type` 与 `size`)

### Requirement: 默认静默与 logging 组件策略
系统 SHALL 保持“无配置=无观测输出”.
诊断 fallback logger 默认关闭;仅在显式启用 logging 组件(或显式 fallback 策略)时输出.
logging 渲染策略(如 `logger|pretty`)MUST 作为 logging 组件配置而非额外入口开关.

#### Scenario: 未启用 logging 无输出
- **WHEN** 未启用 observability/logging 且未注入组件
- **THEN** 执行过程 MUST 不输出观测日志

### Requirement: capture 模式支持 adaptive 回放
系统 MUST 支持与 `adaptive` 并发结合的 capture 模式:worker 只记录 typed payload 与 `Event` envelope,提交点回放.
Observer capture 缓存 MUST 有上限并具备明确超限策略(raise 或确定性丢弃),顺序必须可复现.
Hook capture 当前实现为任务内事件列表记录(无全局硬上限);调用方应通过任务规模与并发配置控制其内存占用.

#### Scenario: capture 模式不执行用户回调
- **WHEN** hub/manager 处于 capture 模式
- **THEN** emit MUST 仅记录事件,不直接执行用户 hook/observer 回调

### Requirement: hooks 与 observer managers 必须按内部职责拆分
系统 MUST 允许将 `HookManager` 与 `ObserverManager` 的“订阅注册管理、handler 解析/缓存、高频事件分发、状态恢复”拆分为内部职责子模块,不得继续要求这些职责长期聚合在 `hooks/base.py` 与 `ob/manager.py` 单一热点文件内.

#### Scenario: managers 拆分后职责可审计
- **WHEN** 维护者重构 `HookManager` 或 `ObserverManager` 的内部结构
- **THEN** 注册、缓存、分发、状态恢复职责 MUST 可区分并独立审阅
- **AND** 不得重新把上述职责聚回单一热点实现

### Requirement: managers 内部拆分后必须保持行为语义稳定
系统 MUST 在 `HookManager` / `ObserverManager` 内部拆分后继续保持 wants 语义、缓存复用语义、线程安全语义与 pickle roundtrip 语义稳定.

#### Scenario: managers 行为语义保持稳定
- **WHEN** 完成 managers 内部职责拆分后运行相关测试
- **THEN** wants、缓存复用、线程安全与 pickle roundtrip 行为 MUST 与重构前保持一致

### Requirement: HookManager 与 ObserverManager 的内部职责拆分必须可审计
系统 MUST 将 `HookManager` 与 `ObserverManager` 的“订阅注册管理、handler 解析/缓存、高频事件分发、状态恢复”视为独立职责,并允许通过内部子模块组织这些职责,而不是继续在单一热点文件中无限聚合.

#### Scenario: 内部职责可以拆入子模块
- **WHEN** 维护者重构 `HookManager` 或 `ObserverManager` 的内部实现
- **THEN** 系统 MUST 允许将注册、缓存、分发、状态恢复拆入内部子模块
- **AND** 不得要求这些职责继续长期共存于单一热点文件中

### Requirement: Hook 与 Observer 管理器重构后必须保持稳定入口与行为语义
系统 MUST 在 `HookManager` / `ObserverManager` 内部拆分后继续保持稳定导入入口与既有行为语义,至少包括: wants 语义、缓存复用语义、线程安全语义与 pickling 后锁恢复语义.

#### Scenario: 稳定入口继续可用
- **WHEN** 调用方继续通过既有稳定入口导入 `HookManager` 或 `ObserverManager`
- **THEN** 导入 MUST 成功
- **AND** 调用方不应被要求迁移到新的内部私有路径

#### Scenario: 行为语义保持稳定
- **WHEN** 完成内部职责拆分后运行现有 hooks / observer 管理器相关测试
- **THEN** wants、缓存复用、线程安全与 pickle roundtrip 语义 MUST 与重构前保持一致
