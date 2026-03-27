# explicit-extension-points Specification

**状态: ✅ 已实现**
## Purpose
定义 PROJECT_NAME 内部扩展点的显式注入与编译式分发模型,减少模块级“魔法注入”与事件热路径反射,提升类型友好性、可维护性与性能稳定性.
## Related Code (as implemented)
- `src/IMPL_ROOT/execution/pipeline/overrides.py` (`PipelineOverrides`)
- `src/IMPL_ROOT/execution/adaptive/policy.py` / `src/IMPL_ROOT/execution/adaptive/tuning.py`
- `src/IMPL_ROOT/hooks/base.py` (`HookManager`)
- `src/IMPL_ROOT/ob/observer.py` (`EventDispatchObserver`)
- `src/IMPL_ROOT/ob/components.py` (`split_components`)
## Requirements
### Requirement: 执行层扩展点必须显式注入
系统 MUST 提供显式的 overrides/config 对象用于覆盖 execution pipeline 的可变实现细节(例如批次切分策略与 `adaptive` 调度策略/并发池配置/执行器类型),并禁止通过 `sys.modules` 探测或模块级 `getattr` “魔法注入”实现覆盖.
默认情况下,未提供 overrides 时系统行为 MUST 与现有默认实现一致.

#### Scenario: 覆盖批次切分策略
- **WHEN** 用户提供自定义 `chunk_iterable` overrides
- **THEN** Pipeline 必须使用该 chunker 进行批次切分

#### Scenario: 注入 adaptive tuning/policy
- **WHEN** 用户通过 overrides 注入 `AdaptiveTuning` 或 `AdaptivePolicy`
- **THEN** `parallel_mode=adaptive` 的调度 MUST 使用该 tuning/policy 决定并发行为

#### Scenario: 覆盖 adaptive 执行器类型
- **WHEN** 用户通过 overrides 注入自定义的 `adaptive` thread backend executor(thread 的 factory 或等价扩展点)
- **THEN** 调度器 MUST 使用该 executor 创建并发 worker
- **AND** 若用户配置/策略选择到 process/async backend,系统 MUST 失败并说明当前仅支持 thread

### Requirement: HookManager 分发在注册阶段编译缓存
系统 MUST 在 hook 注册/注销时编译并缓存事件分发 callables,使 emit 热路径不依赖 `getattr/hasattr` 查找 handler.
缓存结构 SHOULD 以 `event_type -> tuple[(hook, handler_callable)]` 的形式存在,并在 hooks 变更时重建.

#### Scenario: emit 热路径无需 getattr 查找 handler
- **WHEN** HookManager 触发已订阅事件的 emit
- **THEN** 分发应直接调用缓存的 handler_callable,而不是在 emit 中 `getattr(hook, handler_name)`

### Requirement: EventDispatchObserver 需缓存 handler callable
系统 SHALL 使 `EventDispatchObserver.on_event` 在首次遇到某 event_type 时解析 handler,并缓存 bound method,后续事件分发不得重复执行 `getattr` 查找.

#### Scenario: handler 缓存命中
- **WHEN** 同一 observer 连续收到相同 `event_type` 的多个事件
- **THEN** 该 observer 在第二次及之后的分发中应复用缓存的 handler callable

### Requirement: 禁止通过私有字段反射获取跨模块状态
系统 MUST 为跨模块所需状态提供公开、类型化的查询接口,并禁止通过 `getattr(obj, "_private", ...)` 等方式窥探私有字段来决定行为(例如判断 allowlist 是否配置).
该要求不适用于已明确作为“受控动态边界”的 resolver 动态解析过程与安全 compute eval 过程(它们保持现状).

#### Scenario: allowlist 状态通过公开接口查询
- **WHEN** 转换/执行逻辑需要判断 resolver 是否配置 allowlist
- **THEN** 必须通过公开接口完成判断,不得读取 resolver/policy 的私有字段

### Requirement: components/subscribers 装配入口必须显式校验
系统 MUST 在组件列表装配入口(例如 by_yaml runtime 的 `components`/`subscribers`、或 `InstrumentationHub.register`)对每个组件做显式校验:
- `Observer` 组件走 observer 注册路径
- `IExecutionHook` 组件走 hook 注册路径
- 其它对象 MUST 抛出 `TypeError` 并包含组件 index/type 与期望类型

#### Scenario: 错误组件尽早失败
- **WHEN** 用户向 components 列表传入非 `Observer`/非 `IExecutionHook` 的对象
- **THEN** 系统在装配阶段抛出 `TypeError`,避免静默兜底与晚期排错
