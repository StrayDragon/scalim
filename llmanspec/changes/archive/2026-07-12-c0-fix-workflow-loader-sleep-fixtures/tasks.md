## 1. Event-gated loader fixtures

- [x] 1.1 重写 `tests/fixtures/workflow_loaders.py`：用 `threading.Event` gate 替代 `time.sleep`，提供 hold/release/reset API
- [x] 1.2 `reset_counters()` 同时重置 timing gates；导出 `preload_calls` / hold / release 辅助函数

## 2. Test isolation + callers

- [x] 2.1 在 `tests/yaml_dsl/test_yaml_dsl_workflow.py` 添加 autouse fixture 重置 counters/gates
- [x] 2.2 更新 pipeline overlap 用例：hold `main_very_slow`，由 b 的 releasing loader 释放并证明 overlap
- [x] 2.3 确认其它引用 slow/very_slow/table_c_slow 的用例在默认 open-gate 下仍通过；budget 用例改为 Event 同步

## 3. Verification

- [x] 3.1 运行相关 pytest（含 pipeline/stage_barrier/slow loader 相关用例；关键路径多跑几次）
- [x] 3.2 `uv run python scripts/check-no-test-sleep.py --check`（ALLOWLIST 已清空本 fixture）
- [x] 3.3 `llman sdd validate c0-fix-workflow-loader-sleep-fixtures --strict --no-interactive`
- [x] 3.4 `just qa`
