## 1. Code Contract Comments

- [x] 1.1 在 `ExecutionRuntime` 的共享缓存字段附近补齐 `NOTE:` / `WARN:` 注释,明确其在 `adaptive` 下被多线程读写且仅承诺 CPython+GIL
- [x] 1.2 在 `LoadRefExecutionContext` 的 `default_applied_counts` 与 `normalize_key` 缓存写入点补齐同样的 `NOTE:` / `WARN:` 注释(指向“check-then-act / read-modify-write”风险)
- [x] 1.3 在 `load_ref_cache` 写入点与 once-logging set 的写入点补齐 `NOTE:` 注释,说明并发下的语义(例如可能导致重复 loader 调用但不应崩溃)

## 2. Specs

- [x] 2.1 为 `parallel-execution` 增加增量规范(本 change 已创建 delta spec),确保明确声明 CPython+GIL-only 契约

## 3. Verification

- [x] 3.1 运行 `just openspec-check` 确认 OpenSpec 工件合法
- [x] 3.2 运行 `just qa` 确认无行为回归(应为 0 语义变更)
