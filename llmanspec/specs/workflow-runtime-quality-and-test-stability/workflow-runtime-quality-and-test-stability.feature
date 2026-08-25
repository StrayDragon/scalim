# language: zh-CN
# capability: workflow-runtime-quality-and-test-stability
# purpose: 定义 workflow runtime 的质量与测试稳定性要求,包括依赖注入契约、规则 SSOT 复用与并发测试的确定性护栏. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: workflow-runtime-quality-and-test-stability

  @req:r96 @human
  场景: workflow entrypoints MUST support dependency injection without module-global mut
    - 系统 MUST 支持对 workflow 执行关键依赖（至少包括 `run_ir` 与 demand 编译回调）进行**每次调用级别**的显式依赖注入（用于单测与内部替换）,且该机制 MUST 不通过写模块全局变量实现,以保证并发执行可预期。 建议通过 `IMPL_ROOT.dsl.yaml_dsl.workflow_entrypoints.run_workflow(..., run_ir_fn=..., compile_demand_yaml_fn=...)`（或等价入口）完成注入。

  @req:r338 @human
  场景: JSON-like validation MUST be centralized as SSOT
    - 系统 MUST 将 “JSON-like 校验” 收敛为单一 SSOT 实现,并在 workflow ctx 与缓存签名等路径复用,以避免规则漂移导致的不可预期行为或错误信息不一致。

  @req:r460 @human
  场景: concurrency tests MUST be deterministic and avoid wall-clock flakiness
    - 系统的并发/诊断类测试 MUST 避免依赖极小的真实时间阈值与 time.sleep 驱动,并提供足够的 timeout 与明确的完成信号,以降低 CI 抖动导致的 flaky 或误报死锁。事件顺序断言 MUST 优先使用 Event.seq(单调序号)而非 wall-clock Event.timestamp。为保证可重复+可诊断,系统 MUST 同时满足: - 正向等待的超时阈值 MUST 通过测试 SSOT 常量统一管理(例如 CI_TIMEOUT_S) - 负向断言的超时阈值 MUST 使用单独常量(例如 NEGATIVE_TIMEOUT_S) - 当等待发生超时/卡死时,测试 SHOULD 输出足够诊断信息

  @req:r545 @human
  场景: tests MUST avoid time.sleep-driven scheduling and polling loops for synchronization
    - 当测试用例需要等待某个并发事件发生时,测试 MUST 使用事件驱动的同步机制(例如 threading.Event/Barrier)来表达明确完成信号,并避免以下 flaky 模式: - 通过 time.sleep(0.01/0.05) 推进时序 - 通过轮询共享列表/队列+ sleep 的 busy-wait - 使用微小 wall-clock 阈值做不会发生断言。共享 workflow loader fixtures MUST 用 Event-gate 替代真实 sleep,并提供可重置的释放控制。
  @req:r96 @human
  场景: injected-executor-does-not-cross-contaminate-concurrent-runs
    - 必须成立：当 两个并发的 workflow 执行分别使用不同的注入执行器/编译回调；那么 每次执行 MUST 只调用其自身注入的依赖,不得互相污染
    当 两个并发的 workflow 执行分别使用不同的注入执行器/编译回调
    那么 每次执行 MUST 只调用其自身注入的依赖,不得互相污染
  @req:r338 @human
  场景: non-finite-float-is-rejected-consistently
    - 必须成立：当 任一路径对 JSON-like 值校验遇到非有限 float（`NaN/Inf`）；那么 系统 MUST fail-fast 且错误信息 MUST 可用于定位输入路径
    当 任一路径对 JSON-like 值校验遇到非有限 float（`NaN/Inf`）
    那么 系统 MUST fail-fast 且错误信息 MUST 可用于定位输入路径

  @req:r460 @human
  场景: workflow-node-order-uses-seq
    - 必须成立：假如 workflow 并发测试记录 WORKFLOW_NODE_START/END 事件；当 断言节点 b 在节点 a 结束后启动(或与 x 重叠)；那么 断言 MUST 比较 Event.seq 而非 Event.timestamp
    假如 workflow 并发测试记录 WORKFLOW_NODE_START/END 事件
    当 断言节点 b 在节点 a 结束后启动(或与 x 重叠)
    那么 断言 MUST 比较 Event.seq 而非 Event.timestamp

  @req:r545 @human
  场景: workflow-loader-fixtures-use-event-gates
    - 必须成立：假如 tests/fixtures/workflow_loaders.py 提供 slow/very_slow loader；当 workflow 并发测试需要可控时序；那么 loader MUST 通过 threading.Event gate 等待释放,不得 time.sleep
    假如 tests/fixtures/workflow_loaders.py 提供 slow/very_slow loader
    当 workflow 并发测试需要可控时序
    那么 loader MUST 通过 threading.Event gate 等待释放,不得 time.sleep
