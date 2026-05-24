# Proposal: fix-timestamp-test-assertions

## Why

`tests/yaml_dsl/test_yaml_dsl_workflow.py` 中至少 4 处使用 wall-clock `Event.timestamp`（`time.time()` 产生）做排序断言：

```python
assert by_start["b"].timestamp >= by_end["a"].timestamp
assert by_start["b"].timestamp < by_end["x"].timestamp
```

这些断言依赖线程调度时序和 wall-clock 精度，在高负载 CI（`-n auto`）中是 #1 flake 来源。同文件已有正确的 `seq`-based 做法（如 line 1630: `by_start["b"].seq > by_end["a"].seq`）。

## What Changes

1. 将 `test_yaml_dsl_workflow.py:1681-1682` 的 timestamp 断言替换为 `seq`-based
2. 将 `test_yaml_dsl_workflow.py:1735-1736` 的 timestamp 断言替换为 `seq`-based
3. 审查同文件其他可能的 timestamp 排序断言并统一为 `seq`-based

## Capabilities

### Modified Capabilities

- `workflow-runtime-quality-and-test-stability` — 消除 wall-clock 依赖

## Impact

- **代码区域**: `tests/yaml_dsl/test_yaml_dsl_workflow.py`
- **破坏性**: 无 — 仅测试代码
- **测试稳定性**: P0 flake 消除
