## Why

c40 设计了"禁止 tests/ 下使用 `time.sleep` 轮询"的治理门禁，但该门禁脚本未实现。当前仍有 3 处 `time.sleep` 残留：
- `tests/workflow/test_workflow_resources_coverage.py`（`sleep(0.001)` 轮询循环）
- `tests/ob/test_viz_hook.py`（`sleep` 在 hook 路径）
- `tests/fixtures/workflow_loaders.py`（模拟慢加载器）

无门禁意味着新增的 `time.sleep` 轮询无法被自动捕获，c40 的设计意图无法长期维持。

## What Changes

- 修复残留的 `time.sleep` 轮询：
  - `test_workflow_resources_coverage.py`：将 sleep 轮询替换为 `threading.Event` 协调。
  - `test_viz_hook.py`：评估是否可用 event 替代。
- `tests/fixtures/workflow_loaders.py` 中的 sleep 用于模拟慢加载，属于合理用途，加入允许列表。
- 新增治理脚本 `scripts/check-no-test-sleep.py`（或等效 grep/ruff 规则），扫描 `tests/` 下的 `time.sleep` 使用并拒绝未在允许列表中的调用。
- 将该检查集成到 `just qa` 流程。

## Capabilities

### New Capabilities

### Modified Capabilities
- `testing-quality`: 新增 time.sleep 治理门禁。

## Impact

- 测试文件：2-3 个文件需要重构轮询模式。
- CI 流程：`just qa` 增加一个检查步骤。
