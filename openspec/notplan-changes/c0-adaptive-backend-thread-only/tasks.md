## 1. Thread-only adaptive pool

- [ ] 1.1 在 `src/scalim/execution/pipeline/base/_adaptive_pool.py` 保留 `policy.choose_backend(...)` 调用,但仅允许 thread;若返回 process/async 则抛 `ValueError` 且错误信息包含“backend 已裁剪/当前仅支持 thread/如需回加请恢复对应实现模块与测试”。
- [ ] 1.2 收敛 pool 创建逻辑为 `ThreadPoolExecutor`(移除 `ProcessPoolExecutor`/`ThreadLoopExecutor` 路径),并保留 `PipelineOverrides.adaptive_executor_cls` 注入点(用于 thread executor 替换)。

## 2. 保留 seam,删除实现

- [ ] 2.1 `src/scalim/execution/adaptive/policy.py`: 保留 `AdaptivePolicy.choose_backend()` 接口与 `ADAPTIVE_BACKEND_THREAD/PROCESS/ASYNC` 常量,默认策略仍返回 thread。
- [ ] 2.2 `src/scalim/execution/adaptive/loadref_scheduler.py`: 保留 backend 分发结构形状,但仅实现 thread 路径;删除 process/async 分支、pickle 检查、process failure_mode 相关逻辑与 helper 引用。
- [ ] 2.3 删除 async backend 实现与测试: `src/scalim/execution/adaptive/thread_loop_executor.py`、`tests/test_thread_loop_executor.py`。
- [ ] 2.4 删除 process backend 实现与支持代码: `run_task_in_process(...)` 相关模块/函数与所有引用点(包含 scheduler/pool/support 文件)。

## 3. Overrides 收敛

- [ ] 3.1 `src/scalim/execution/pipeline/overrides.py`: 移除 `adaptive_process_executor_cls` / `adaptive_async_executor_cls` 字段及其引用,避免保留无效接口面。

## 4. Tests 回归与新增

- [ ] 4.1 改写所有依赖 process/async backend 的测试为 thread-only 覆盖:`tests/test_adaptive_execution_tuning.py`、`tests/test_execution_pipeline.py`、`tests/test_internal_branch_coverage_guards.py`。
- [ ] 4.2 新增回归测试:当 policy 选择 process/async 时,`maybe_create_adaptive_pool(...)` 稳定抛 `ValueError` 且错误信息清晰(至少断言关键子串)。
- [ ] 4.3 新增回归测试:当 runtime 中 `adaptive_backend` 被设置为 process/async 时,`AdaptiveLoadRefScheduler.execute_segment(...)` 稳定抛 `ValueError` 且错误信息清晰(至少断言关键子串)。

## 5. Docs 与生成物边界

- [ ] 5.1 更新 `docs/doc/architecture/parallel-modes.md`(手写 SSOT)删除 process/async 细节,保留“backend seam + 当前仅支持 thread”的描述;若文件包含 `BEGIN/END AUTOGEN` 注入区块,仅修改区块外内容。
- [ ] 5.2 如变更影响到生成页或注入区块,运行 `just gen-docs` 刷新生成物(SSOT 为生成入口,不手改任何 `.gen.` 文件与注入区块内部),并用 `just qa`/CI drift gate 验收无漂移。

## 6. Verification

- [ ] 6.1 `uv run pytest -q` thread-only 全量回归。
- [ ] 6.2 `just openspec-check`(sanitize + `openspec validate --all --strict --no-interactive`)确保 OpenSpec 工件可发布。
