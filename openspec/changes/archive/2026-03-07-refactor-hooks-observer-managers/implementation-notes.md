## phase 1 职责盘点

### HookManager
- 稳定入口保留在 `src/IMPL_ROOT/hooks/base.py`.
- phase 1 内部职责拆分为:
  - `src/IMPL_ROOT/hooks/_internal/manager_registry.py`: register / unregister / clear
  - `src/IMPL_ROOT/hooks/_internal/manager_subscriptions.py`: typed/on_event 订阅推断与热路径缓存
  - `src/IMPL_ROOT/hooks/_internal/manager_events.py`: typed trigger / on_event dispatch / fallback 行为
  - `src/IMPL_ROOT/hooks/_internal/manager_state.py`: pickle roundtrip、锁恢复、采样策略状态
- 继续由 facade 暴露 `IExecutionHook`、`BaseHook`、`HookManager` 与兼容 warning 常量.

### ObserverManager
- 稳定入口保留在 `src/IMPL_ROOT/ob/manager.py`.
- phase 1 内部职责拆分为:
  - `src/IMPL_ROOT/ob/_internal/manager_registry.py`: observer 注册、supports/wants 缓存重建
  - `src/IMPL_ROOT/ob/_internal/manager_emit.py`: 高频事件分发、fallback warning、close/capture replay 发射
  - `src/IMPL_ROOT/ob/_internal/manager_capture.py`: capture manager / recorded event 流程
  - `src/IMPL_ROOT/ob/_internal/manager_state.py`: pickle roundtrip、锁恢复、采样/overflow 策略状态
- facade 继续暴露 `ObserverManager`、`ObserverCaptureOverflowError` 与兼容 warning 常量.

## phase 1 模块布局结论
- 本轮不改 `HookManager` / `ObserverManager` 的推荐导入路径,只做 facade + `_internal` 子模块拆分.
- 本轮不扩展到 YAML runtime、viz、adaptive 等其它热点;这些由独立 change 继续治理.
- phase 1 的最小接口是: facade 仍负责构造与公开类型名,内部模块负责注册、缓存、分发、状态恢复.

## 保护性测试映射
- 稳定入口与 phase 1 pickle 守护: `tests/test_hook_observer_manager_phase1_guards.py`
- hooks 缓存/dispatch/采样与 fallback: `tests/test_hook_manager_dispatch.py`, `tests/test_hooks.py`
- observer wants/capture/overflow/pickle: `tests/test_observer.py`, `tests/test_observer_manager_capture_event_limit.py`, `tests/test_pickling_parallel_managers.py`
- 线程安全热路径: `tests/test_thread_safety.py`, `tests/test_observability_fastpath.py`

## 外部消费者检查(脱敏)
- 已检查一个受控外部消费者中的相关调用点,未发现其直接导入 `HookManager` 或 `ObserverManager` 稳定入口.
- 因此外部消费者在本 change 下无需适配;若未来需要接入,仍应通过公开 facade,不暴露 `_internal` 路径.

## phase 边界说明
- 本 change 仅覆盖 managers 内部职责拆分与兼容性守护.
- `VizObserver`、YAML runtime、adaptive scheduler 等其它热点模块不在本 change 内继续扩 scope.
