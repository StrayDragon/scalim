## Why

c35 引入了 `CI_TIMEOUT_S` / `NEGATIVE_TIMEOUT_S` / `POLL_DEADLINE_S` 作为测试超时 SSOT，但部分测试文件仍使用硬编码超时值。例如：
- `test_workflow_cache_pool.py` 使用 module-level `_TIMEOUT_S = 5.0` 和 `wait(timeout=0.1)`。
- `test_workflow_entrypoints_smoke.py` 使用 `30.0`。
- `test_viz_hook.py` 使用 `5.0`。

这些硬编码值在 CI 负载较高时容易产生 flaky failures，且与 SSOT 设计意图不一致。

## What Changes

- 将所有 `tests/` 下的硬编码超时替换为 `CI_TIMEOUT_S` / `NEGATIVE_TIMEOUT_S` / `POLL_DEADLINE_S`。
- 将 `test_workflow_cache_pool.py` 中的 `_TIMEOUT_S` 和 `wait(timeout=0.1)` 替换为 `event_wait` + `CI_TIMEOUT_S` helper。
- 对于确实需要非标准超时的场景，增加注释说明原因。
- 可选：添加治理测试扫描 `tests/` 下的 `timeout=` 字面量，确保使用 SSOT 常量。

## Capabilities

### New Capabilities

### Modified Capabilities
- `testing-quality`: 超时值 SSOT 统一覆盖范围扩展。

## Impact

- 涉及 `tests/workflow/test_workflow_cache_pool.py`、`tests/ob/test_viz_hook.py` 等多个测试文件。
- 依赖 `tests/support/testing_utils.py` 已有 helper。
