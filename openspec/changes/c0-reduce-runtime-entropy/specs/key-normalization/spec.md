## ADDED Requirements

### Requirement: key_normalization MUST propagate into adaptive per-task runtimes
当系统为 `parallel_mode=adaptive` 创建 per-task 子运行时(例如调度器为每个 `LoadRef(keys)` 任务创建隔离 runtime/context 并在提交点回放事件)时,子运行时 MUST 继承本次运行的 `key_normalization` 值,并使用相同的规范化规则参与匹配与诊断.

#### Scenario: adaptive per-task runtime uses the same normalization mode as the parent run
- **GIVEN** 本次运行 `key_normalization="auto_str"`(或 `"force_str"`)
- **WHEN** 系统在 adaptive 下创建 per-task 子运行时并执行 `LoadRef(keys)`
- **THEN** 子运行时 MUST 使用与父运行时相同的 `key_normalization` 值
- **AND** 任何依赖 key_normalization 的命中/告警语义 MUST 与 `seq` 等价

