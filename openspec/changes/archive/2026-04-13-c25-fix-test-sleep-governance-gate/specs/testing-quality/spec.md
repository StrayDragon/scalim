# testing-quality (delta) Specification

## ADDED Requirements

### Requirement: `time.sleep` in tests MUST be governed with an explicit allowlist

`tests/**/*.py` 中 MUST NOT 使用 `time.sleep` 作为轮询或“等待条件成立”的手段；此类同步 MUST 改用 `threading.Event`（或等价）配合 `event_wait` 等 SSOT helper。

以下用途 MAY 保留 `time.sleep`，但 MUST 被列入治理脚本的显式允许列表并具备可审阅理由（例如模拟慢加载的 fixture）：

- `tests/fixtures/workflow_loaders.py` 等用于**模拟慢 I/O/慢加载器**的 fixture 中的 `time.sleep`，MUST 通过允许列表排除。

系统 MUST 提供可独立运行的扫描入口（例如 `scripts/check-no-test-sleep.py`），在 `--check` 模式下对未允许的 `time.sleep` 返回非零退出码；该检查 MUST 接入 `just qa`（例如 `quick-check-only-py` 链），以防止回归。

#### Scenario: polling loop uses event coordination

- **WHEN** 测试需要等待另一线程写入文件或更新共享状态
- **THEN** 测试 MUST 使用写入方 `Event.set()` 与读取方 `event_wait(...)`（或等价），而不得使用 `while` + `time.sleep` 轮询

#### Scenario: unauthorized sleep fails the gate

- **WHEN** 维护者在未列入允许列表的 `tests/` 模块中新增 `time.sleep` 调用
- **THEN** `just qa` 中的 sleep 治理检查 MUST 失败并报告文件与位置

#### Scenario: documented fixture sleep remains allowed

- **WHEN** `tests/fixtures/workflow_loaders.py`（或允许列表中明确列出的路径）使用 `time.sleep` 模拟慢加载
- **THEN** 治理扫描 MUST 将该命中视为允许且不阻断 `just qa`
