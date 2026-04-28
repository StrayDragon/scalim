## ADDED Requirements

### Requirement: non-bench tests MUST be xdist-parallel-safe

系统 MUST 确保所有非 bench 测试在 `pytest-xdist` 并行执行(例如 `pytest -n auto`)下稳定通过,且不依赖执行顺序或隐式全局状态耦合。

因此,所有非 bench 测试 MUST 满足:
- 在 `pytest -n auto` 下稳定通过(不允许依赖执行顺序)
- 测试不得通过“修改模块全局状态但未隔离/未加锁”的方式制造隐式耦合
- 若确需修改模块全局状态(例如 demo/misc 模块提供的全局配置),测试 MUST 通过集中化的隔离工具实现,并确保在并行执行下不会跨测试污染(必要时通过锁序列化)

#### Scenario: repo QA gate passes under xdist
- **WHEN** 运行 `just qa`
- **THEN** 非 bench 测试 MUST 在 `pytest -n auto` 下稳定通过

#### Scenario: global-state patches are isolated and restored
- **GIVEN** 某测试需要临时修改一个模块全局状态(例如 demo 的全局 config)
- **WHEN** 测试执行并结束
- **THEN** 修改 MUST 被可靠恢复
- **AND** 并行执行的其它测试不得观察到该修改
