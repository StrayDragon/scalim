## ADDED Requirements

### Requirement: adaptive worker runtimes MUST inherit run-level key_normalization
当 `parallel_mode=adaptive` 创建 worker 子运行时(用于在提交点前执行 `LoadRef(keys)` 的 fan-out/fan-in)时,系统 MUST 继承本次 run-level 的 `key_normalization` 配置到该子运行时,以避免并发路径与串行路径语义漂移.

说明:
- 子运行时内部可以使用 `parallel_mode="seq"` 执行单个任务以保持确定性,但其 key space 语义 MUST 与父运行时一致。
- 该要求不改变 `key_normalization` 的算法,仅要求“配置传播”一致。

#### Scenario: key_normalization affects adaptive load_ref semantics consistently
- **GIVEN** 本次运行启用 `key_normalization="force_str"`
- **AND** 某个 `LoadRef` 在串行路径下会因字符串规范化而命中目标 mapping
- **WHEN** 相同输入改为 `parallel_mode=adaptive` 执行
- **THEN** adaptive worker 的 lookup 命中/缺失语义 MUST 与串行路径一致
- **AND** 系统 MUST NOT 因子运行时回退到默认 `raw` 而产生额外的 miss

### Requirement: adaptive per-task runtimes MUST inherit observability config via capture managers
当 `parallel_mode=adaptive` 创建 per-task 子运行时(用于执行单个 `LoadRef(keys)` 任务并在提交点回放事件)时,系统 MUST 继承本次 run-level 的诊断/可观测性配置,避免并发路径与串行路径在“是否产生日志/事件/诊断”的语义上漂移。

说明:
- 子运行时 MUST 从父 runtime 派生 `HookManager`/`ObserverManager` 的 capture manager(而不是新建默认 manager)。
- 继承范围至少包括 `fallback_logger_enabled`、debug 开关、loader result 策略以及同一 run 口径的元信息(例如 `run_id`)。

#### Scenario: adaptive per-task runtime keeps the same observability toggles as the parent run
- **GIVEN** 本次运行启用 `fallback_logger_enabled`
- **AND** 本次运行存在特定的 hook/observer 订阅与 loader result 策略
- **WHEN** 系统在 adaptive 下创建 per-task 子运行时并执行 `LoadRef(keys)`
- **THEN** 子运行时 MUST 使用与父运行时一致的诊断开关与订阅发现口径
- **AND** 子运行时产生的 hook/observer 事件 MUST 可在提交点被 capture+replay(与串行路径可比对)
