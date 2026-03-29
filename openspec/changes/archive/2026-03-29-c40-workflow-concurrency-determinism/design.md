## Context

workflow 并发执行会在多个线程同时：
- 触发 instrumentation emit（hook/observer 回调链路）
- 写入/合并共享资源（csv/workbook/sheetbook）
- 产出 viz 输出（JSONL/附件/快照）

现有护栏（`no-external-callback-under-lock`）已经要求“回调必须在锁外”，但这会引入一个新的问题：锁外回调天然可能并发触发，除非系统提供序列化语义或明确要求 observer 自己线程安全。

参考借鉴（原则层面）：
- Dagster 的事件/日志模型倾向于“先结构化记录，再统一消费/展示”，本质上是一种 capture+replay（或队列化）思路，有利于并发下的确定性与可回放。

## Goals / Non-Goals

**Goals:**
- 默认情况下 observers/viz 输出在并发下安全（不交错、不损坏、语义可解释）。
- 共享资源写入结果确定：与声明顺序一致，可复现。
- 不破坏“回调不得在锁内”的死锁护栏。

**Non-Goals:**
- 不引入复杂的跨进程分布式锁服务（只做低成本文件锁/进程内队列）。
- 不一次性重新设计整个事件 catalog（以行为硬化为主）。

## Decisions

### 1) Observer 并发语义：默认序列化（或 capture+replay）

决策（优先序）：
1) **capture+replay（推荐默认）**：并发执行阶段将事件写入线程安全队列（或 per-run 缓冲），在一个单线程 drain 阶段按确定顺序回放给 observers。
2) 若需要近实时输出，提供 **per-observer 锁** 的序列化调用策略（仍在锁外，但对每个 observer 互斥）。

理由：
- capture+replay 能同时满足：线程安全 + 确定顺序 + 可重放（与 replay bundle/viz 方向一致）。
- per-observer 锁实现简单，作为可选 fallback。

### 2) Viz/落盘写入：单写者语义

决策：
- `VizEventEmitter` 写 JSONL/文件时必须具备单写者语义：
  - 要么 emitter 内部加锁；
  - 要么仅允许在 replay/drain 阶段由单线程调用。

理由：
- JSONL 行交错会直接破坏产物可解析性，且难以事后修复。

### 3) 共享资源确定性：以声明顺序决定 commit 顺序

决策：
- 对每条写入意图（write intent / segment）记录一个稳定的 `decl_order`（例如：按 runs 列表顺序为一级、writes 列表顺序为二级的序号）。
- commit 阶段对同一资源的 segments 按 `decl_order` 稳定排序后写入；禁止依赖并发完成时序。
- sheet 顺序同理：以声明顺序或显式排序规则决定，而非“首次创建时 append”。

理由：
- 将并发不确定性从“结果层”隔离到“执行层”，保证输出可复现。

### 4) 写锁默认策略与锁文件语义

决策：
- 对最终输出（csv/workbook/sheetbook export）默认启用写锁（低成本 lock 文件），避免跨进程静默覆盖。
- 锁文件内容写入 owner 信息（workflow_exec_id/run_id/pid/timestamp），并在冲突时提供可操作诊断。
- 提供可控的清理策略（force-unlock/TTL）以应对崩溃残留锁导致的“伪竞态”。

### 5) run_id 生成：改为高熵唯一值

决策：
- `run_id` 由 `uuid4`（或等价高熵方案）生成，避免毫秒时间碰撞导致目录/文件争用。

## Risks / Trade-offs

- [性能] capture+replay 会增加事件缓存：→ 提供可配置的 buffer 上限与 drop 策略（仅对 viz/高频事件），并默认只对必要事件 capture。
- [行为变化] 写锁默认启用可能让原本“最后写入者覆盖”的场景变成 fail-fast：→ 文档明确恢复建议（唯一路径/关闭锁/外部协调）。
- [顺序语义] 以声明顺序为 SSOT 可能与部分用户“完成越早越先写”的直觉不同：→ 明确以可复现为优先；并提供显式 opt-in 的“按完成顺序”模式（若确有需求）。

## Migration Plan

- 阶段 1：引入 decl_order 并在 commit 阶段排序；补齐确定性回归测试（并发执行多次结果一致）。
- 阶段 2：实现 observer capture+replay 或 per-observer 序列化；确保 viz 产物在并发下可解析。
- 阶段 3：加强锁文件语义与 run_id 生成；补充诊断与文档。

## Open Questions

- 默认策略选 capture+replay 还是 per-observer 锁？（倾向 capture+replay；但需要评估实时性需求。）
- force-unlock/TTL 的入口放在 CLI 还是仅作为内部 API？

