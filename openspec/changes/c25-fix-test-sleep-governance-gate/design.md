## Context

c40 的设计意图是消除 `tests/` 中的 `time.sleep` 轮询并建立治理门禁。当前残留 3 处 sleep（其中 1 处是合理的模拟用途），且门禁脚本未实现。

约束：
- `time.sleep` 在测试 fixtures 中模拟慢操作是合理用途，需要允许列表
- 门禁必须集成到 `just qa` 以防止回归

## Goals / Non-Goals

**Goals:**
- 修复残留的 sleep 轮询
- 实现治理门禁脚本
- 集成到 QA 流程

**Non-Goals:**
- 不禁止所有 `time.sleep`（模拟慢操作是合理用途）

## Decisions

### 1) 修复残留 sleep 轮询

**`test_workflow_resources_coverage.py`：**
将 `while True: try read_latest(); except FileNotFoundError: sleep(0.001)` 轮询替换为 `threading.Event` 协调——由写入方在完成后 `set()`，读取方 `event_wait()`。

**`test_viz_hook.py`：**
评估 sleep 用途。如果是等待异步 IO，改为 `event_wait`；如果是等待文件写入（原子替换），改为 retry + `event_wait` 组合。

### 2) 允许列表

`tests/fixtures/workflow_loaders.py` 中的 `time.sleep(0.05)` 用于模拟慢数据加载器，是合理的测试 fixture 用途。在治理脚本中通过允许列表排除。

### 3) 治理脚本

新增 `scripts/check-no-test-sleep.py`：
- 扫描 `tests/**/*.py` 中的 `time.sleep` 调用
- 排除允许列表中的文件（`tests/fixtures/workflow_loaders.py`）
- 非零退出码表示发现未授权的 sleep 使用
- 集成到 `just qa` 的 `quick-check-only-py` 链中

## Risks / Trade-offs

- 将 sleep 轮询改为 event 协调需要修改测试结构，但提高了可靠性和执行速度。

## Migration Plan

- 修复 2 个轮询文件
- 实现治理脚本
- 更新 justfile
- 验证：`just qa`

## Open Questions

- 无。
