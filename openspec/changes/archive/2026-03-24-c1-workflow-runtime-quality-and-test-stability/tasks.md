## 1. Refactors (Maintain Semantics)

- [x] 1.1 拆分 `src/scalim/dsl/by_yaml/runtime/workflow_execute.py:run_workflow` 为阶段化单元（prepare/execute/commit/report），减少圈复杂度与 `# noqa C901` 集中度。
- [x] 1.2 拆分 `src/scalim/dsl/by_yaml/workflow_config.py:load_workflow_config_from_mapping` 的解析/校验逻辑,按段落收敛（resources/runs/writes/cache_pool/deps）。
- [x] 1.3 拆分 `src/scalim/dsl/by_yaml/runtime/workflow_resources_sheetbook.py` 的大函数（对齐/预算/导出）以提升可读性与可测性。

## 2. Contracts / SSOT

- [x] 2.1 移除 `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py` 通过写模块全局变量注入依赖的方式,改为显式注入（并更新相关测试替换点）。
- [x] 2.2 合并 JSON-like 校验为 SSOT helper,并在 `workflow_execute` 与 `workflow_cache_pool` 等路径复用,避免 drift。

## 3. Test Stability

- [x] 3.1 稳定化 `tests/test_preload_cache.py`：用事件同步替代 `time.sleep()`，避免 0.01s 等小阈值驱动断言,并减少对日志次数的脆弱断言。
- [x] 3.2 稳定化死锁检测类测试：提升 `join/wait` timeout 并使用完成信号（`tests/test_workflow_cache_pool.py`、`tests/test_workflow_resources_coverage.py`）。
- [x] 3.3 为 `tests/test_deterministic_ordering.py` 的 `subprocess.check_output` 增加 timeout,避免 suite 卡死。

## 4. Gates

- [x] 4.1 通过门禁：`just qa`
- [x] 4.2 通过门禁：`just openspec-check`
