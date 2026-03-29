## Why

workflow 并发执行（ThreadPoolExecutor / max_concurrency）与可观测性（observers/viz 落盘）叠加后，当前实现存在典型并发风险：

- observer 回调的线程安全契约不明确：同一 observer 可能被多线程并发调用，导致状态错乱、漏事件或输出损坏。
- viz/事件落盘缺少并发写入保护：JSONL/文件写入可能交错，产物不可解析。
- 共享资源写入（csv/workbook/sheetbook）在并发场景下的写入顺序与 sheet 顺序可能随调度漂移，违反“声明顺序决定结果”的可复现性预期。
- 跨进程写同一路径的默认锁策略偏弱，可能出现静默覆盖或损坏；锁文件残留也会造成“伪竞态”失败。

这些问题会直接影响框架作为“可重复的报表/管道执行引擎”的可信度，需要把并发语义与确定性写入升级为明确的 SSOT 契约，并对实现做硬化。

## What Changes

- 明确并实现 observer/事件分发的并发语义：默认保证线程安全（序列化回调或 capture+replay），并保持 no-external-callback-under-lock 护栏不被破坏。
- viz 输出与事件落盘增加并发保护（锁/队列），确保产物在并发下仍然可解析。
- 共享输出资源写入顺序与 sheet 顺序确定化：以 workflow YAML 声明顺序（runs + writes）作为 SSOT，而非线程调度完成顺序。
- 强化写锁与锁文件语义：对最终输出默认启用并发写保护；锁文件包含 owner/时间戳并提供更友好的诊断（必要时支持 force-unlock/TTL）。
- `run_id` 生成改为更强唯一性（避免毫秒碰撞导致目录/文件争用）。

## Capabilities

### New Capabilities

- `observer-concurrency-contract`: 明确 observers/hook/event emitter 的并发语义与默认保障（序列化或 capture+replay）。

### Modified Capabilities

- `workflow-shared-output-containers`: 落地“写入顺序由声明顺序决定、且对同一资源写入互斥/串行化”的确定性要求。
- `no-external-callback-under-lock`: 在不把回调放回锁内的前提下，补齐“锁外回调仍具备线程安全/确定性”的实现策略。
- `flow-visualization` / `workflow-replay-bundle`: viz 产物在并发下保持可解析、可重放。

## Impact

- 受影响代码（SSOT）：`src/scalim/workflow/execute.py`、`src/scalim/ob/_internal/manager_emit.py`、`src/scalim/ob/presets/_internal/viz_output.py`、`src/scalim/workflow/resources_*.py`（csv/workbook/sheetbook 写入/commit/锁）、`src/scalim/events/_event.py`（run_id）。
- 受影响测试：并发回归、确定性回归（多次并发执行结果一致）、viz 产物可解析性回归。
- 受影响文档：workflow 并发与可观测性文档（SSOT 在 `docs/doc/**`；生成/注入区块通过 `just gen-docs` 刷新）。

