## 0. Gates / Verification (Self-Check)

- [x] 0.1 运行生成入口并确认无 drift：`just gen`
- [x] 0.2 运行全量质检并通过：`just qa`
- [x] 0.3 并发相关用例压力验证（可选）：`pytest tests/test_thread_safety.py tests/test_adaptive_capture_replay.py -n 0 --count=100`

## 1. P0 - Safety / Data Integrity

- [x] 1.1 修复 `WorkflowCachePool` 逐出与加载竞态（`src/scalim/execution/workflow_cache_pool.py`）
- [x] 1.2 `trusted_allow_all_modules` 增加环境变量门控（`src/scalim/dsl/by_yaml/runtime/references.py`）
- [x] 1.3 `unsafe_run/unsafe_compile` 增加审计日志与弃用警告（`src/scalim/dsl/by_yaml/runtime/unsafe_entrypoints.py`）

## 2. P1 - Reliability / Thread Safety / Privacy

- [x] 2.1 `PreloadCache` 并发路径与容器写入线程安全（`src/scalim/execution/preload_cache.py`）
- [x] 2.2 `ThreadLoopExecutor` submit/shutdown 加锁（`src/scalim/execution/adaptive/thread_loop_executor.py`）
- [x] 2.3 `SecureComputeEngine.compile` LRU 缓存并发安全（`src/scalim/dsl/by_yaml/config_parsing/security.py`）
- [x] 2.4 审计回调 PII 脱敏 + 错误消息表达式哈希化（`src/scalim/dsl/by_yaml/config_parsing/security.py`）
- [x] 2.5 统一测试超时常量，替换硬编码超时（`tests/testing_utils.py` + 相关测试）
- [x] 2.6 `builtin_callables` 解析复用主 allowlist（`src/scalim/dsl/by_yaml/runtime/compiler.py`）

## 3. P2 - Maintainability / Quality

- [x] 3.1 拆分 C901 热点：outputs/workflow_compile/execute（`src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 等）
- [x] 3.2 分批收窄宽泛异常（优先 sinks；`src/scalim/sinks/*`）
- [x] 3.3 TOCTOU 文件操作改为 EAFP（workflow resources/sinks）
- [x] 3.4 fixture 隔离：module-scoped fixture 增加状态恢复（`tests/conftest.py`）
