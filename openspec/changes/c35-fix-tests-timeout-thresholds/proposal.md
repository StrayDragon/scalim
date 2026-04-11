## Meta

- Type: `fix-0`
- Topic: 多处测试使用 `timeout=1.0/2` 的线程同步，CI 抖动下易 flaky；建议统一收敛到 `CI_TIMEOUT_S`
- Related code (代表性点位):
  - `tests/execution/test_thread_safety.py:83` / `:93` / `:130` / `:140`（`Barrier.wait(timeout=1.0)`）
  - `tests/execution/test_adaptive_execution_tuning.py:250`（`Event.wait(timeout=1.0)`）
  - `tests/yaml_dsl/test_yaml_dsl_lsp_cache.py:89`~`:101`（多处 `timeout=2`）
  - 统一超时常量：
    - `tests/support/testing_utils.py:12`（`CI_TIMEOUT_S`）
    - `tests/support/testing_utils.py:13`（`NEGATIVE_TIMEOUT_S`）

## 背景

仓库测试默认开启较重的运行方式（xdist 并行 + coverage，见 `pyproject.toml`），这会显著增加：

- 线程调度延迟；
- import 与覆盖率插桩开销；
- I/O 竞争；

从而放大“1 秒级别”的时间敏感测试的偶发失败概率。

目前在若干测试中存在紧凑超时（1s/2s）用于线程同步（Barrier/Event/join）。这类测试在本机通常稳定，但在 CI 高负载/并行下容易误报超时，形成 flaky。

## 现状与问题

### 现状

以 `tests/execution/test_thread_safety.py` 为例：

- `start.wait(timeout=1.0)` 假设 1 秒内两个线程都能启动并到达 barrier；
- 但在 CI 抢占严重时，线程启动与调度可能超过 1 秒，导致 `BrokenBarrierError` 并失败。

`tests/execution/test_adaptive_execution_tuning.py:250` 也类似：

- worker thread `finish.wait(timeout=1.0)` 假设主测试线程 1 秒内 set；
- 但 coverage/xdist/GC 叠加可能导致主线程迟迟未 set，误报超时。

`tests/yaml_dsl/test_yaml_dsl_lsp_cache.py`：

- `proceed.wait(timeout=2)` 与 `fut.result(timeout=2)` 在慢机器或文件系统抖动下可能不足。

### 问题本质

这些测试的目标是验证“线程安全/并发去重/调度策略”，而不是验证“在 1 秒内必须完成”。把业务断言绑在很小的 wall-clock timeout 上，会把 CI 抖动误当成业务失败。

## 目标

- 消除“过小 timeout”导致的 flaky；
- 保持测试覆盖目标不变（仍验证并发行为）；
- 让超时可配置（CI 与本地可不同）。

## 推荐修复方案

### 方案 A：统一将正向等待超时改用 `CI_TIMEOUT_S`（不推荐）

做法：

- 将 `timeout=1.0`、`timeout=2`、`join(timeout=1.0)` 等正向等待统一替换为：
  - `CI_TIMEOUT_S`（默认 10s，可通过 `SCALIM_TEST_TIMEOUT` 调整）
- 将“应该不发生”的负向断言使用 `NEGATIVE_TIMEOUT_S`（默认 2s）或更小但仍可配置的常量。

优点：

- 改动小、收益大；
- 不改变断言语义，只是减少环境敏感性；
- 所有测试可以通过环境变量统一调节。

缺点：

- CI 在真实死锁时会等待更久才失败（但这通常是可接受的；也可在死锁路径加更好的诊断输出）。

### 方案 B：封装线程同步 helper，统一输出诊断信息（推荐）

做法：

- 在 `tests/support/` 引入 helper：
  - `wait_or_dump_threads(event, timeout, label)`：超时后打印线程栈/状态，便于定位；
  - `barrier_wait(barrier, timeout)`：统一处理 BrokenBarrierError 并输出诊断。

优点：

- 一旦真的卡死，排障更快。

缺点：

- 需要写少量通用代码。

### 方案 C：增加轻量 gate，禁止回归到硬编码小超时与 sleep/polling（推荐作为 A/B 的补强）

做法：

- 增加一个可重复运行的扫描 gate（脚本或 just 任务），检查 `tests/**` 是否出现易 flaky 模式：
  - 硬编码的极小 timeout（例如 `timeout=1.0`、`timeout=2`）
  - `time.sleep(0.01/0.05)` 驱动的轮询等待
- 允许通过显式 allow 标记做局部豁免（避免误伤确有必要的用例）

优点：

- 防止未来新增测试再次引入同类 flaky；
- 让治理从“修一次”升级为“长期不回归”。

缺点：

- 需要维护规则与 allow 机制（但可以保持很轻量）。

## 性价比

- 方案 A：极高（典型 fix-0）。
- 方案 B：高（增强可观测性，降低排障成本）。
- 方案 C：高（长期治理收益大，且与 A/B 可叠加）。

## 验证建议

- 选取最易 flaky 的 2~3 个测试文件（`test_thread_safety.py`、`test_adaptive_execution_tuning.py`、`test_yaml_dsl_lsp_cache.py`）重复运行 10 次：
  - `pytest -n 0 -q <file> -k <subset>`（先排除 xdist 干扰）
  - 再在默认 addopts 下跑一次（模拟 CI）
- 观察：超时失败率应降为 0。
