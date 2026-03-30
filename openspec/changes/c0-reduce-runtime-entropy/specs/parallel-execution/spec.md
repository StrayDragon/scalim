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

