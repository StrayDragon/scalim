# language: zh-CN
# capability: governance-extension-points
# purpose: 定义 PROJECT_NAME 内部扩展点的显式注入与编译式分发模型，减少模块级”魔法注入”与事件热路径反射，提升类型友好性、可维护性与性能稳定性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: governance-extension-points

  @req:r49 @human
  场景: 执行层扩展点必须显式注入
    - 系统 MUST 提供显式的 overrides/config 对象用于覆盖 execution pipeline 的可变实现细节(例如批次切分策略与 `adaptive` 调度策略/并发池配置/执行器类型),并禁止通过 `sys.modules` 探测或模块级 `getattr` “魔法注入”实现覆盖. 默认情况下,未提供 overrides 时系统行为 MUST 与现有默认实现一致.

  @req:r293 @human
  场景: HookManager 分发在注册阶段编译缓存
    - 系统 MUST 在 hook 注册/注销时编译并缓存事件分发 callables,使 emit 热路径不依赖 `getattr/hasattr` 查找 handler. 缓存结构 SHOULD 以 `event_type -> tuple[(hook, handler_callable)]` 的形式存在,并在 hooks 变更时重建.

  @req:r417 @human
  场景: EventDispatchObserver 需缓存 handler callable
    - 系统 SHALL 使 `EventDispatchObserver.on_event` 在首次遇到某 event_type 时解析 handler,并缓存 bound method,后续事件分发不得重复执行 `getattr` 查找. 缓存的 typed handler callable 的入参 MUST 为完整 `Event` envelope（与 hooks-observability-structure r217 一致），不得仅缓存/分发 `event.payload`。

  @req:r512 @human
  场景: 禁止通过私有字段反射获取跨模块状态
    - 系统 MUST 为跨模块所需状态提供公开、类型化的查询接口,并禁止通过 `getattr(obj, "_private", ...)` 等方式窥探私有字段来决定行为(例如判断 allowlist 是否配置). 该要求不适用于已明确作为“受控动态边界”的 resolver 动态解析过程与安全 compute eval 过程(它们保持现状).

  @req:r589 @human
  场景: components/subscribers 装配入口必须显式校验
    - 系统 MUST 在组件列表装配入口(例如 yaml_dsl runtime 的 `components`/`subscribers`、或 `InstrumentationHub.register`)对每个组件做显式校验: - `Observer` 组件走 observer 注册路径 - `IExecutionHook` 组件走 hook 注册路径 - 其它对象 MUST 抛出 `TypeError` 并包含组件 index/type 与期望类型
  @req:r49 @human
  场景: 覆盖批次切分策略
    - 必须成立：当 用户提供自定义 `chunk_iterable` overrides；那么 Pipeline 必须使用该 chunker 进行批次切分
    当 用户提供自定义 `chunk_iterable` overrides
    那么 Pipeline 必须使用该 chunker 进行批次切分

  @req:r49 @human
  场景: 注入-adaptive-策略
    - 必须成立：当 用户通过 overrides 注入自定义的 adaptive 策略；那么 调度器 MUST 使用该策略决定并发行为
    当 用户通过 overrides 注入自定义的 adaptive 策略
    那么 调度器 MUST 使用该策略决定并发行为

  @req:r49 @human
  场景: 覆盖执行器类型
    - 必须成立：当 用户通过 overrides 注入自定义的执行器；那么 调度器 MUST 使用该执行器创建并发 worker
    当 用户通过 overrides 注入自定义的执行器
    那么 调度器 MUST 使用该执行器创建并发 worker
  @req:r293 @human
  场景: emit-热路径无需动态查找
    - 必须成立：当 HookManager 触发已订阅事件的 emit；那么 分发应直接调用缓存的 handler callable，而不是在 emit 中动态查找
    当 HookManager 触发已订阅事件的 emit
    那么 分发应直接调用缓存的 handler callable，而不是在 emit 中动态查找
  @req:r417 @human
  场景: handler-缓存命中
    - 必须成立：当 同一 observer 连续收到相同 `event_type` 的多个事件；那么 该 observer 在第二次及之后的分发中应复用缓存的 handler callable
    当 同一 observer 连续收到相同 `event_type` 的多个事件
    那么 该 observer 在第二次及之后的分发中应复用缓存的 handler callable
  @req:r512 @human
  场景: 跨模块状态通过公开接口查询
    - 必须成立：当 模块需要查询另一模块的状态；那么 必须通过公开接口完成判断，不得读取私有字段
    当 模块需要查询另一模块的状态
    那么 必须通过公开接口完成判断，不得读取私有字段
  @req:r589 @human
  场景: 错误组件尽早失败
    - 必须成立：当 用户向 components 列表传入非 `Observer`/非 `IExecutionHook` 的对象；那么 系统在装配阶段抛出 `TypeError`,避免静默兜底与晚期排错
    当 用户向 components 列表传入非 `Observer`/非 `IExecutionHook` 的对象
    那么 系统在装配阶段抛出 `TypeError`,避免静默兜底与晚期排错
