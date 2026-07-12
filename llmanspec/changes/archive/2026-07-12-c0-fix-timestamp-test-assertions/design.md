## Context

`tests/yaml_dsl/test_yaml_dsl_workflow.py` 中 pipeline / stage_barrier 用例用 `Event.timestamp`（`time.time()`）断言节点启动顺序，在 CI `-n auto` 下易 flake。同文件 DAG 用例已用 `Event.seq`。

## Decisions

1. **因果顺序用 `seq`**：`depends_on` / `stage_barrier` 等“必须先结束后再开始”的断言用单调 `Event.seq`（严格 `>`）。
2. **并发重叠不用 `seq` 也不用 `timestamp`**：`pipeline` 的“b 在 x 结束前启动”是 wall-clock overlap 语义；在并发 emit 下 `seq` 与 `timestamp` 都可能错位。该断言改由 `c0-fix-workflow-loader-sleep-fixtures` 的 Event-gate 证明（hold `very_slow` 直至观察到 `b` START 再 release）。
3. **范围**：本 change 只改本文件内 ordering 断言口径；不改 runtime 事件模型。

## Risks / Non-goals

- pipeline overlap 的最终稳定断言依赖同批次的 sleep-fixtures change；两者应一起验证。
- 不引入 fake clock。
