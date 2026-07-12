## Context

`tests/fixtures/workflow_loaders.py` 用真实 `time.sleep(0.05~0.2)` 制造 slow/very_slow 时序，被大量 workflow 测试引用；在高负载 CI 下不稳定，且会被 `scripts/check-no-test-sleep.py` 门禁约束。

同仓库已有 Event/Barrier 模式（`test_workflow_cache_pool.py`、`tests/support/testing_utils.py`）。

## Goals / Non-Goals

Goals:
- 用 `threading.Event` gate 替代 fixture 内真实 sleep。
- 默认 gate 打开（不阻塞），保持大多数用例行为等同“瞬时 loader”。
- 需要可控时序的用例显式 `hold_*` / `release_*`。
- autouse 重置 `_PRELOAD_CALLS` 与 timing gates，避免漏重置。
- 从 `scripts/check-no-test-sleep.py` ALLOWLIST 移除本 fixture。

Non-Goals:
- 不改 production runtime。
- 不引入 fake clock 到 loader fixtures。

## Decisions

1. **Gate API**（模块级，线程安全）:
   - `reset_timing()`：所有 gate `set()`（打开）并清空 entered 信号 / barrier
   - `hold_*` / `release_*`：控制 `main_slow` / `main_very_slow` / `preload` / `table_c`
   - loader 内 `event_wait(..., timeout_s=CI_TIMEOUT_S)`
2. **`reset_counters()`** 同时调用 `reset_timing()`。
3. **pipeline overlap**：不可依赖 `WORKFLOW_NODE_START` Observer（`max_concurrency>1` + components 时 `capture_observability` 会延后回放事件）。改用 `load_main_fast_releasing_very_slow`：b 的 main loader 释放 x 的 very_slow gate。
4. **cache budget**：`hold_main_slow` 保持首节点 in-flight；monkeypatch `_ensure_budget_for_new_entry` 在第二次触发时 `Event.set()`；观察到 budget fail 后再 `release_main_slow`，避免 executor teardown 死等。
5. **autouse**：`tests/yaml_dsl/test_yaml_dsl_workflow.py` function-scoped 重置 counters/gates。

## Risks

- 需可控时序的新用例必须显式 hold/release；默认 open-gate 不再“自然变慢”。
