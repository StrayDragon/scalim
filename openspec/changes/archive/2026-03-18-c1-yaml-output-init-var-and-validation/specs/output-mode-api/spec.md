## ADDED Requirements

### Requirement: 成功路径 sink.close 失败必须使 run 失败
系统 MUST 将 sink 的 close 视为输出落盘/提交的最终阶段.
当 `engine.run(...)` 已成功完成时,`run_ir` MUST 调用 `sink.close()` 并将其异常向上传播,不得返回“成功”的 `ExecutionResult`.

#### Scenario: run 成功但 close 失败导致 run_ir 失败
- **GIVEN** `engine.run(...)` 成功完成
- **WHEN** `sink.close()` 在 close 阶段抛出异常
- **THEN** `run_ir(...)` MUST 失败并抛出该异常

### Requirement: 异常路径 close 不得覆盖原异常
当 `engine.run(...)` 在执行中抛异常时,系统 MUST best-effort 调用 `sink.close()` 做清理,但 close 异常 MUST NOT 覆盖原始执行异常.

#### Scenario: engine.run 抛异常且 close 同时失败
- **GIVEN** `engine.run(...)` 抛出异常 `E1`
- **WHEN** `sink.close()` 额外抛出异常 `E2`
- **THEN** `run_ir(...)` MUST 抛出 `E1`(不得被 `E2` 覆盖)

