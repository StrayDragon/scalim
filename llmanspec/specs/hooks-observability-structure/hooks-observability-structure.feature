# language: zh-CN
# capability: hooks-observability-structure
# purpose: 定义 Hook/Observer/事件体系的统一边界:事件契约、分发路径、组件装配与高频路径性能语义. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: hooks-observability-structure

  @req:r56 @human
  场景: 观测事件契约以 EventType 与公开 payload 为中心
    - 系统 MUST 以 `events` 作为事件定义中心。执行层、hooks、observers MUST 通过统一 `Event` envelope 交互。进程内事件身份 MUST 为 `EventType`（不得以作者面 `str` 作为订阅/envelope 身份）。系统 MUST 将稳定的 typed payload 数据类作为公开契约从 `scalim.events`（或其公开 re-export 面）导出：docs/examples/skills 等用户可见材料 MUST 示范公开导入路径，MUST NOT 依赖 `scalim.events._events` 等私有模块作为长期契约。用户侧订阅 MUST 使用 `EventType`；handler MUST 能以公开 payload 类型消费 `Event.payload`。

  @req:r300 @human
  场景: InstrumentationHub 是执行层唯一事件投递边界
    - 系统 MUST 通过 `InstrumentationHub` 统一分发到 hooks/observers. `wants(event_type)=false` 时 MUST 快速短路:不得构建 payload、不得构建 `Event` envelope、不得进入热路径额外开销.

  @req:r423 @human
  场景: 组件列表是对外唯一装配入口
    - 系统 MUST 通过统一 `components` 列表装配 hooks/observers;不得通过新增运行入口 bool 开关切换实现. 组件列表 MUST 支持混合 `Observer` 与 `IExecutionHook`.

  @req:r517 @human
  场景: 执行层与观测层解耦
    - 系统 MUST 保持执行层仅依赖事件契约与分发器,不直接 import 具体观测实现. execution 入口 MUST 消费 DSL-agnostic 的组件装配结果,不直接依赖 YAML 专有观测类型.

  @req:r593 @human
  场景: 观测预设实现必须分离采集建模与展示职责
    - 系统 MUST 将 observability 预设实现按"事件采集、数据建模、展示/导出"职责分离组织,避免单个预设模块长期同时承载三类职责.

  @req:r647 @human
  场景: HookManager 必须将注册管理与分发策略解耦
    - 系统 MUST 将 HookManager 的"订阅注册管理"与"事件分发策略"视为独立职责并保持实现解耦,防止单一基类持续增长.

  @req:r691 @human
  场景: 事件分发热路径以缓存 callable 为主
    - 系统 MUST 在 HookManager 高频事件分发路径避免每次 `emit` 执行 `getattr/hasattr` 反射查找,并在注册阶段编译/缓存 callables 后直接分发. Observer 分发路径 MAY 使用"首次事件懒绑定 + 后续缓存复用"的策略;该一次性反射查找不应在后续同类事件重复发生.

  @req:r729 @human
  场景: Hook 的 on_event 与 typed 回调不互斥
    - 系统 MUST 将 `IExecutionHook.on_event(Event)` 视为额外订阅方式,不得因实现 `on_event` 而禁用 typed 回调. 当 hook 同时实现 typed 与 `on_event`,系统 SHOULD 同时触发二者.

  @req:r761 @human
  场景: wants 语义仅表示订阅者存在
    - 系统 MUST 保持 `wants(event_type)` 仅表示订阅者存在,不得混入 fallback logger 等副作用策略.

  @req:r142 @human
  场景: Loader/Diagnostic 事件负载结构稳定
    - 系统 MUST 提供稳定的 Loader 与 diagnostic 事件负载字段. Loader 事件 MUST 支持 `full|summary|sample|none` 策略,且 `sample_size>=1`;`cache_status=hit` 时 MUST NOT 触发实际 loader 调用. diagnostic warning payload 至少包含 `message`、`source_id`、`field_id`、`lookup_key`、`row_id`.

  @req:r165 @human
  场景: 默认静默与 logging 组件策略
    - 系统 SHALL 保持"无配置=无观测输出". 诊断 fallback logger 默认关闭;仅在显式启用 logging 组件(或显式 fallback 策略)时输出. logging 渲染策略(如 `logger|pretty`)MUST 作为 logging 组件配置而非额外入口开关.

  @req:r185 @human
  场景: capture 模式支持 adaptive 回放
    - 系统 MUST 支持与 `adaptive` 并发结合的 capture 模式:worker 只记录 typed payload 与 `Event` envelope,提交点回放. Observer capture 缓存 MUST 有上限并具备明确超限策略(raise 或确定性丢弃),顺序必须可复现. Hook capture 当前实现为任务内事件列表记录(无全局硬上限);调用方应通过任务规模与并发配置控制其内存占用.

  @req:r203 @human
  场景: hooks 与 observer managers 必须按内部职责拆分
    - 系统 MUST 允许将 `HookManager` 与 `ObserverManager` 的"订阅注册管理、handler 解析/缓存、高频事件分发、状态恢复"拆分为内部职责子模块,不得继续要求这些职责长期聚合在单一热点文件内.

  @req:r221 @human
  场景: managers 内部拆分后必须保持行为语义稳定
    - 系统 MUST 在 `HookManager` / `ObserverManager` 内部拆分后继续保持 wants 语义、缓存复用语义、线程安全语义与 pickle roundtrip 语义稳定.

  @req:r234 @human
  场景: workflow attribution meta is injected incrementally and wants-gated
    - 系统 MUST 支持在 `Event.meta` 中注入 workflow 归因字段: - `workflow_exec_id`: 标识一次 workflow 执行(一次调用内稳定) - `workflow_node_id`: 标识事件来自哪个 workflow 节点(对 demand 节点等于 workflow YAML 的 `runs[*].id`) 归因注入 MUST 通过"增量合并 meta"实现: - MUST NOT 改写既有 `Event.run_id` 语义(仍表示一次 demand 执行) - MUST NOT 改写既有 `Event.seq` 语义(仍由发送端在 `run_id` 内单调递增) 归因注入 MUST wants-gated: - 当事件不会被发送到 observers 或 `hook.on_event(Event)` 路径时,MUST 不构建 `Event` envelope,也 MUST 不做 meta 注入/复制.

  @req:r245 @human
  场景: workflow attribution meta keys are reserved and override must fail fast
    - `workflow_exec_id` 与 `workflow_node_id` MUST 视为保留 key. 当系统已注入这些字段时,若用户/下游组件试图在同一次事件分发中覆盖同名 key,系统 MUST fail-fast 抛出错误,避免归因被悄悄篡改导致观测数据不可解释.

  @req:r254 @human
  场景: workflow event namespace is reserved for future extensions
    - 系统 MUST 将 workflow-level 事件与未来扩展事件纳入统一事件目录,并保留以下稳定命名空间前缀: - `workflow_node_*` - `workflow_cache_*` - `workflow_resource_*` 后续变更在新增 workflow/cache/resource 事件时 MUST 复用上述前缀与归因字段,以保证可稳定 join 回 workflow DAG 视图.

  @req:r261 @human
  场景: High-cardinality diagnostics MUST be wants-gated at the callsite
    - 系统 MUST 对高基数诊断路径提供"调用点 wants-gated"语义：当 `InstrumentationHub.wants(event_type)=false` 时，执行层 MUST 不进行与数据规模成正比的诊断计算与中间结构构造（不仅仅是不构造 `Event` envelope）。 该要求适用于但不限于： - `relation_lookup`（逐行命中/缺失诊断） - 其它可能出现 `O(row_count)` 或 `O(key_count)` 的诊断/观测辅助逻辑

  @req:r268 @human
  场景: events public facade MUST expose EventType as identity SSOT
    - 系统 MUST 为用户提供结构化的事件类型访问方式（可枚举/可检索的事件目录，以及按主题分组的稳定入口）。`EventType` MUST 作为进程内事件身份的唯一 SSOT。系统 MAY 在落盘/JSONL/viz 等边界将 `event_type` 编码为稳定的 builtin `str`（来自 `EventType` 成员值），但读回进程内 `Event` 时 MUST 归一为 `EventType`。系统 MUST NOT 将边界字符串形态宣称为二开注册/订阅的作者面。

  @req:r930 @human
  场景: Observer and Hook registration MUST be EventType-strict
    - 系统 MUST 将 `Observer.event_types` 与 Hook 的 `event_types` 定义为 `Optional[Set[EventType]]`（或等价 Enum 集合）。注册/校验路径 MUST 只接受 `EventType` 成员；传入裸 builtin `str` 或其他非 `EventType` 元素时 MUST fail-fast。错误信息 SHOULD 指向事件目录或列出允许成员。`supports_unknown_event_types` MAY 作为显式逃生口保留，但 MUST NOT 作为公开二开文档的默认扩展方式；推荐扩展路径 MUST 为向事件目录登记新的 `EventType` 成员。

  @req:r931 @human
  场景: In-process emit and wants MUST use EventType identity
    - 系统 MUST 使 `InstrumentationHub`/`ObserverManager`/`HookManager` 的 `wants`/`emit`/分发索引在进程内以 `EventType` 为事件身份（不得要求调用方传入作者面 `str` 作为唯一合法类型）。`wants(event_type)=false` 时的短路语义（不构建 payload/envelope）MUST 保持不变。

  @req:r932 @human
  场景: AGENTS Event identity exception MUST be documented as SSOT
    - 仓库级 `AGENTS.md`（Policy SSOT 段）MUST 明确：Event/Hook 注册与 `Event` envelope 的进程内身份以 `EventType` 为准，不适用「输出/存储必须为 builtin str」对该域进程内表示的约束；边界编码 `.value` 仅用于落盘/流式导出且读回须归一为 `EventType`。

  @req:r217 @human
  场景: typed Observer and Hook handlers MUST receive Event envelope
    - 系统 MUST 使 `EventDispatchObserver` 的 typed `on_*` 分发与 `IExecutionHook`/`HookManager` 的 typed 回调接收完整 `Event` envelope（不得仅传入 `event.payload`）。handler MUST 经 `Event.payload` 消费公开 payload 类型，并 MUST 能读取同次分发的 `Event.meta`（含横切键如 `scalim_compute_phase` 与 workflow 归因字段）。系统 MUST NOT 长期提供「payload 与 Event 双签名」兼容分发。`IExecutionHook.on_event(Event)` 与 typed 回调的并存语义（r729）MUST 保持不变。

  @req:r56 @human
  场景: public-payload-import
    - 必须成立：当 用户编写自定义 Observer handler；那么 MUST 能从 `scalim.events` 公开导入 payload 类型，MUST NOT 需要 `scalim.events._events`
    当 用户编写自定义 Observer handler
    那么 MUST 能从 `scalim.events` 公开导入 payload 类型，MUST NOT 需要 `scalim.events._events`

  @req:r56 @human
  场景: subscribe-with-event-type
    - 必须成立：当 用户声明订阅集；那么 MUST 使用 `EventType` 成员（例如 `EventType.PIPELINE_START`），不得以作者面字符串字面量作为推荐写法
    当 用户声明订阅集
    那么 MUST 使用 `EventType` 成员（例如 `EventType.PIPELINE_START`），不得以作者面字符串字面量作为推荐写法
  @req:r300 @human
  场景: 无订阅者时无副作用
    - 必须成立：当 未注册订阅者且触发某事件 `emit(...)`；那么 系统 MUST 不调用回调且不构建高成本 payload
    当 未注册订阅者且触发某事件 `emit(...)`
    那么 系统 MUST 不调用回调且不构建高成本 payload
  @req:r423 @human
  场景: 追加组件即可订阅
    - 必须成立：当 用户在 components 中追加一个 hook 或 observer；那么 该组件 MUST 在对应事件触发时收到回调
    当 用户在 components 中追加一个 hook 或 observer
    那么 该组件 MUST 在对应事件触发时收到回调
  @req:r517 @human
  场景: execution-编排不依赖-yaml-观测模型
    - 必须成立：当 审阅 execution 编排入口的 imports/参数类型；那么 不应直接 import/依赖 `ObservabilityConfig` 等 YAML 专有配置类型
    当 审阅 execution 编排入口的 imports/参数类型
    那么 不应直接 import/依赖 `ObservabilityConfig` 等 YAML 专有配置类型
  @req:r593 @human
  场景: 展示层替换不影响采集契约
    - 必须成立：当 维护者替换或调整可视化/导出实现；那么 事件采集契约 MUST 保持稳定
    当 维护者替换或调整可视化/导出实现
    那么 事件采集契约 MUST 保持稳定

  @req:r593 @human
  场景: 采集策略调整不破坏展示输入契约
    - 必须成立：当 维护者调整采集策略实现；那么 输出给展示层的中间模型契约 MUST 保持稳定
    当 维护者调整采集策略实现
    那么 输出给展示层的中间模型契约 MUST 保持稳定
  @req:r647 @human
  场景: 扩展分发策略不影响订阅注册
    - 必须成立：当 新增或调整事件分发策略；那么 订阅注册语义 MUST 保持不变
    当 新增或调整事件分发策略
    那么 订阅注册语义 MUST 保持不变
  @req:r691 @human
  场景: hook-高频分发无反射
    - 必须成立：当 高并发/高频事件被触发且存在 hook 订阅者；那么 分发路径应直接调用缓存的 callables,不在每次 emit 中执行 handler 反射查找
    当 高并发/高频事件被触发且存在 hook 订阅者
    那么 分发路径应直接调用缓存的 callables,不在每次 emit 中执行 handler 反射查找

  @req:r691 @human
  场景: observer-首次懒绑定后复用缓存
    - 必须成立：当 observer 首次接收某事件类型；那么 允许一次性解析 handler
    当 observer 首次接收某事件类型
    那么 允许一次性解析 handler
  @req:r729 @human
  场景: 同时订阅-typed-与-on-event
    - 必须成立：当 hook 同时覆写 `on_event` 与 `on_pipeline_start`；那么 触发 pipeline_start 时该 hook 的两条回调路径都应被调用
    当 hook 同时覆写 `on_event` 与 `on_pipeline_start`
    那么 触发 pipeline_start 时该 hook 的两条回调路径都应被调用
  @req:r761 @human
  场景: fallback-不影响-wants
    - 必须成立：当 未注册 hooks/observers 但启用了诊断 fallback logger；那么 `wants(EVENT_DIAGNOSTIC_WARNING)` 仍应为 false
    当 未注册 hooks/observers 但启用了诊断 fallback logger
    那么 `wants(EVENT_DIAGNOSTIC_WARNING)` 仍应为 false
  @req:r142 @human
  场景: summary-负载有效
    - 必须成立：当 loader policy 为 `summary`；那么 loader 事件 payload MUST 返回摘要结构(含 `type` 与 `size`)
    当 loader policy 为 `summary`
    那么 loader 事件 payload MUST 返回摘要结构(含 `type` 与 `size`)
  @req:r165 @human
  场景: 未启用-logging-无输出
    - 必须成立：当 未启用 observability/logging 且未注入组件；那么 执行过程 MUST 不输出观测日志
    当 未启用 observability/logging 且未注入组件
    那么 执行过程 MUST 不输出观测日志
  @req:r185 @human
  场景: capture-模式不执行用户回调
    - 必须成立：当 hub/manager 处于 capture 模式；那么 emit MUST 仅记录事件,不直接执行用户 hook/observer 回调
    当 hub/manager 处于 capture 模式
    那么 emit MUST 仅记录事件,不直接执行用户 hook/observer 回调
  @req:r203 @human
  场景: managers-拆分后职责可审计
    - 必须成立：当 维护者重构 `HookManager` 或 `ObserverManager` 的内部结构；那么 注册、缓存、分发、状态恢复职责 MUST 可区分并独立审阅
    当 维护者重构 `HookManager` 或 `ObserverManager` 的内部结构
    那么 注册、缓存、分发、状态恢复职责 MUST 可区分并独立审阅
  @req:r221 @human
  场景: managers-行为语义保持稳定
    - 必须成立：当 完成 managers 内部职责拆分后运行相关测试；那么 wants、缓存复用、线程安全与 pickle roundtrip 行为 MUST 与重构前保持一致
    当 完成 managers 内部职责拆分后运行相关测试
    那么 wants、缓存复用、线程安全与 pickle roundtrip 行为 MUST 与重构前保持一致
  @req:r234 @human
  场景: demand-events-carry-workflow-attribution-without-changing-ru
    - 必须成立：假如 workflow runner 为某次 demand 执行配置了 workflow attribution 注入；当 demand 执行过程中发出任意 catalog 事件；那么 发给 observers/`hook.on_event` 的 `Event.meta` MUST 包含 `workflow_exec_id` 与 `workflow_node_id`
    假如 workflow runner 为某次 demand 执行配置了 workflow attribution 注入
    当 demand 执行过程中发出任意 catalog 事件
    那么 发给 observers/`hook.on_event` 的 `Event.meta` MUST 包含 `workflow_exec_id` 与 `workflow_node_id`
  @req:r245 @human
  场景: overriding-workflow-attribution-keys-fails-fast
    - 必须成立：假如 系统已为某次 demand 执行启用 attribution 注入；当 调用方尝试在 `Event.meta` 中显式传入 `workflow_exec_id` 或 `workflow_node_id`；那么 系统 MUST 立即抛出错误并指出该 key 为保留字段
    假如 系统已为某次 demand 执行启用 attribution 注入
    当 调用方尝试在 `Event.meta` 中显式传入 `workflow_exec_id` 或 `workflow_node_id`
    那么 系统 MUST 立即抛出错误并指出该 key 为保留字段
  @req:r254 @human
  场景: future-workflow-events-reuse-reserved-prefixes-and-attributi
    - 必须成立：当 后续变更新增一个 workflow/cache/resource 生命周期事件；那么 该事件类型名称 MUST 以 `workflow_node_`/`workflow_cache_`/`workflow_resource_` 之一作为前缀
    当 后续变更新增一个 workflow/cache/resource 生命周期事件
    那么 该事件类型名称 MUST 以 `workflow_node_`/`workflow_cache_`/`workflow_resource_` 之一作为前缀
  @req:r261 @human
  场景: relation-lookup-hit-miss-diagnostics-are-skipped-when-not-wa
    - 必须成立：当 `InstrumentationHub.wants("relation_lookup")=false` 且执行一次包含关联加载的批次；那么 系统 MUST 不执行逐行 hit/miss 分类诊断逻辑
    当 `InstrumentationHub.wants("relation_lookup")=false` 且执行一次包含关联加载的批次
    那么 系统 MUST 不执行逐行 hit/miss 分类诊断逻辑

  @req:r261 @human
  场景: relation-lookup-diagnostics-still-work-when-wanted
    - 必须成立：当 `InstrumentationHub.wants("relation_lookup")=true` 且执行一次包含关联加载的批次；那么 系统 MUST 继续发出 `relation_lookup` 事件并保持既有 payload 结构
    当 `InstrumentationHub.wants("relation_lookup")=true` 且执行一次包含关联加载的批次
    那么 系统 MUST 继续发出 `relation_lookup` 事件并保持既有 payload 结构

  @req:r268 @human
  场景: facade-catalog-enum
    - 必须成立：当 用户从 `scalim.events` 探索可用事件；那么 MUST 通过 `EventType`/目录获得闭集成员，而非依赖散落字符串常量作为身份 SSOT
    当 用户从 `scalim.events` 探索可用事件
    那么 MUST 通过 `EventType`/目录获得闭集成员，而非依赖散落字符串常量作为身份 SSOT

  @req:r268 @human
  场景: boundary-roundtrip
    - 必须成立：当 viz/capture 将事件写入 JSONL 后再载入为进程内 `Event`；那么 边界可含 `event_type` 字符串，但进程内 `Event.event_type` MUST 为 `EventType`
    当 viz/capture 将事件写入 JSONL 后再载入为进程内 `Event`
    那么 边界可含 `event_type` 字符串，但进程内 `Event.event_type` MUST 为 `EventType`

  @req:r930 @human
  场景: reject-bare-str-subscription
    - 必须成立：当 注册 Observer/Hook 且 `event_types` 含裸 `str`；那么 系统 MUST fail-fast 拒绝注册
    当 注册 Observer/Hook 且 `event_types` 含裸 `str`
    那么 系统 MUST fail-fast 拒绝注册

  @req:r930 @human
  场景: accept-event-type-subscription
    - 必须成立：当 注册 Observer/Hook 且 `event_types` 仅为 `EventType` 成员；那么 系统 MUST 接受并按成员分发
    当 注册 Observer/Hook 且 `event_types` 仅为 `EventType` 成员
    那么 系统 MUST 接受并按成员分发

  @req:r931 @human
  场景: wants-short-circuit-preserved
    - 必须成立：假如 无订阅者；当 触发某 `EventType` 的 emit；那么 系统 MUST 不构建高成本 payload 与 `Event` envelope
    假如 无订阅者
    当 触发某 `EventType` 的 emit
    那么 系统 MUST 不构建高成本 payload 与 `Event` envelope

  @req:r932 @human
  场景: agents-documents-exception
    - 必须成立：当 审阅 `AGENTS.md` Policy 段；那么 MUST 包含 Event/Hook 身份以 `EventType` 为进程内 SSOT 的例外说明
    当 审阅 `AGENTS.md` Policy 段
    那么 MUST 包含 Event/Hook 身份以 `EventType` 为进程内 SSOT 的例外说明

  @req:r217 @human
  场景: typed-observer-receives-event-envelope
    - 必须成立：当 Observer 覆写 typed `on_field_compute` 且系统发出带 `meta.scalim_compute_phase` 的 `FIELD_COMPUTE`；那么 typed handler 收到的参数 MUST 为 `Event`，且 `event.meta['scalim_compute_phase']` 与发出时一致；`event.payload` MUST 为 `FieldComputeEvent`
    当 Observer 覆写 typed `on_field_compute` 且系统发出带 `meta.scalim_compute_phase` 的 `FIELD_COMPUTE`
    那么 typed handler 收到的参数 MUST 为 `Event`，且 `event.meta['scalim_compute_phase']` 与发出时一致；`event.payload` MUST 为 `FieldComputeEvent`

  @req:r217 @human
  场景: typed-hook-receives-event-envelope
    - 必须成立：当 Hook 覆写 typed `on_field_compute` 且系统发出带非空 `Event.meta` 的 `FIELD_COMPUTE`；那么 typed handler 收到的参数 MUST 为 `Event`，且可读同一 `Event.meta`；`event.payload` MUST 为公开 `FieldComputeEvent`
    当 Hook 覆写 typed `on_field_compute` 且系统发出带非空 `Event.meta` 的 `FIELD_COMPUTE`
    那么 typed handler 收到的参数 MUST 为 `Event`，且可读同一 `Event.meta`；`event.payload` MUST 为公开 `FieldComputeEvent`

  @req:r217 @human
  场景: typed-and-on-event-both-see-same-envelope
    - 必须成立：当 Hook 同时覆写 typed `on_field_compute` 与 `on_event`；那么 触发 `FIELD_COMPUTE` 时两条路径 MUST 都能访问等价的 `Event.meta`（r729 并存）
    当 Hook 同时覆写 typed `on_field_compute` 与 `on_event`
    那么 触发 `FIELD_COMPUTE` 时两条路径 MUST 都能访问等价的 `Event.meta`（r729 并存）
