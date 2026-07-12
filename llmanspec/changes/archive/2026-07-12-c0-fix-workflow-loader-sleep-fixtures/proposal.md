# Proposal: fix-workflow-loader-sleep-fixtures

## Why

`tests/fixtures/workflow_loaders.py` 使用真实 `time.sleep(0.05~0.2)` 控制 loader 调度时序，被数十个 workflow 测试引用。这编码了对 wall-clock 精度的依赖，在高负载 CI 中导致间歇性失败。

同仓库已有更好的模式：
- `test_workflow_cache_pool.py` 使用 `threading.Event`/`Barrier` 控制
- `test_loader_retry.py` 使用 fake clock + mock sleep

此外，`_PRELOAD_CALLS` 全局计数器仅在部分测试中重置（`reset_counters()`），新增测试容易遗漏。

## What Changes

1. **用 event 驱动替代 sleep**：将 `load_main_slow`、`load_main_very_slow`、`load_preload_table` 等改为使用 `threading.Event` 控制释放时机
2. **提供 fixture 辅助函数**：如 `configure_slow_release(delay_s)` 或 pytest fixture `workflow_loader_timing`
3. **添加 autouse fixture 重置计数器**：在使用 `workflow_loaders` 的测试模块中自动重置 `_PRELOAD_CALLS`
4. **保持行为兼容**：确保时序语义不变，仅消除 wall-clock 依赖

## Capabilities

### Modified Capabilities

- `workflow-runtime-quality-and-test-stability` — 消除 sleep-based 测试
- `testing-quality` — 测试隔离加固

## Impact

- **代码区域**: `tests/fixtures/workflow_loaders.py`, `tests/yaml_dsl/test_yaml_dsl_workflow.py` 相关测试
- **破坏性**: 无 — 仅测试代码
- **测试稳定性**: P0 flake 消除，测试隔离提升
